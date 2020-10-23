pragma solidity ^0.6.9;
pragma experimental ABIEncoderV2;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/math/SafeMath.sol";

import './Interfaces/Compound/CErc20I.sol';
import './Interfaces/Compound/ComptrollerI.sol';

import './Interfaces/UniswapInterfaces/IUniswapV2Router02.sol';

import "./Interfaces/Yearn/IController.sol";

import "./Interfaces/DyDx/DydxFlashLoanBase.sol";
import "./Interfaces/DyDx/ICallee.sol";

import "./Interfaces/Aave/FlashLoanReceiverBase.sol";
import "./Interfaces/Aave/ILendingPoolAddressesProvider.sol";
import "./Interfaces/Aave/ILendingPool.sol";

import "./BaseStrategy.sol";

contract YearnDaiCompStratV2 is BaseStrategy, DydxFlashloanBase, ICallee, FlashLoanReceiverBase {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    /**
    * Events Section
    */   
    /**
     * @notice Event emitted when trying to do Flash Loan
     */
    event Leverage(uint amountRequested, uint amountGiven, bool deficit, address flashLoan);

    address private constant SOLO = 0x1E0447b19BB6EcFdAe1e4AE1694b0C3659614e4e;
    address private constant AAVE_LENDING = 0x24a42fD28C976A61Df5D00D0599C34c4f90748c8;

    // Comptroller address for compound.finance
    ComptrollerI public constant compound = ComptrollerI(0x3d9819210A31b4961b30EF54bE2aeD79B9c9Cd3B); 

    address public constant comp = address(0xc00e94Cb662C3520282E6f5717214004A7f26888);
    address public constant cDAI = address(0x5d3a536E4D6DbD6114cc1Ead35777bAB948E3643);
    address public constant uni = address(0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D);
    // used for comp <> weth <> dai route
    address public constant weth = address(0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2); 

    uint256 public performanceFee = 450;
    uint256 public strategistReward = 50;
    uint256 public constant performanceMax = 10000;

    uint256 public withdrawalFee = 50;
    uint256 public constant withdrawalMax = 10000;

    uint256 public collateralTarget = 0.735 ether;  // 73.5% 
    uint256 public minDAI = 100 ether;
    uint256 public minCompToSell = 0.5 ether;
    bool public active = true;

    bool public DyDxActive = true;
    bool public AaveActive = true;

    constructor(address _vault) public BaseStrategy(_vault) FlashLoanReceiverBase(AAVE_LENDING){}

    /*
     * Liquidate as many assets as possible to `want`, irregardless of slippage,
     * up to `_amount`. Any excess should be re-invested here as well.
     */
    function liquidatePosition(uint256 _amount) internal override {

        uint256 _balance = want.balanceOf(address(this));

        if (_balance < _amount) {
            _amount = _withdrawSome(_amount.sub(_balance));
            _amount = _amount.add(_balance);
        }

         if (_amount > reserve) {
            reserve = 0;
        } else {
            reserve = reserve.sub(_amount);
        }
    }

        
    //This function works out what we want to change with our flash loan
    // Input balance is the amount we are going to deposit/withdraw. and dep is whether is this a deposit or withdrawal        
    function _calculateDesiredPosition(uint256 balance, bool dep) internal view returns (uint256 position, bool deficit) {
        (uint256 deposits, uint256 borrows) = getCurrentPosition();

        //when we unwind we end up with the difference between borrow and supply
        uint unwoundDeposit = deposits.sub(borrows);

        //we want to see how close to collateral target we are. 
        //So we take deposits. Add or remove balance and see what desired lend is. then make difference

        uint desiredSupply = 0;
        if(dep){
            desiredSupply = unwoundDeposit.add(balance);
        }else{
            require(unwoundDeposit >= balance, "withdrawing more than balance");
            desiredSupply = unwoundDeposit.sub(balance);
        }

        //desired borrow is balance x leveraged targed-1. So if we want 4x leverage (max allowed). we want to borrow 3x desired balance
        //1e21 is 1e18 x 1000
        uint leverageTarget = uint256(1e21).div(uint256(1e18).sub(collateralTarget));
        uint desiredBorrow = desiredSupply.mul(leverageTarget.sub(1000)).div(1000);

        //now we see if we want to add or remove balance
        // if the desired borrow is less than our current borrow we are in deficit. so we want to reduce position
        if(desiredBorrow < borrows){
            deficit = true;
            position = borrows.sub(desiredBorrow);
        }else{
            //otherwise we want to increase position
             deficit = false;
            position = desiredBorrow.sub(borrows);
        }

    }

    //returns the current position
    //WARNING - this returns just the balance at last time someone touched the cDAI token. 
    //Does not accrue interest. 
    function getCurrentPosition() public view returns (uint deposits, uint borrows) {
        CErc20I cd = CErc20I(cDAI);
       
        (, uint ctokenBalance, uint borrowBalance, uint exchangeRate) = cd.getAccountSnapshot(address(this));
        borrows = borrowBalance;

        //need to check this:
        deposits =  ctokenBalance.mul(exchangeRate).div(1e18);
    }

        //maxDeleverage is how much we want to reduce by
    function _normalDeleverage(uint256 maxDeleverage) internal returns (uint256 deleveragedAmount) {
        CErc20I cd =CErc20I(cDAI);
        uint lent = cd.balanceOfUnderlying(address(this));

        //we can use storeed because interest was accrued in last line
         uint borrowed = cd.borrowBalanceStored(address(this));
         if(borrowed == 0){
             return 0;
         }

         (, uint collateralFactorMantissa,) = compound.markets(cDAI);
         uint theoreticalLent = borrowed.mul(1e18).div(collateralFactorMantissa);

         deleveragedAmount = lent.sub(theoreticalLent);
        
        if(deleveragedAmount >= borrowed){
            deleveragedAmount = borrowed;
        }
        if(deleveragedAmount >= maxDeleverage){
            deleveragedAmount = maxDeleverage;
        }
        cd.redeemUnderlying(deleveragedAmount);
        
         want.safeApprove(cDAI, 0);
         want.safeApprove(cDAI, deleveragedAmount);

        cd.repayBorrow(deleveragedAmount);

        emit Leverage(maxDeleverage, deleveragedAmount, true, address(0));
    }

    function _withdrawSome(uint256 _amount) internal returns (uint256) {

        (uint256 position, bool deficit) = _calculateDesiredPosition(_amount, false);

        uint256 _before = want.balanceOf(address(this));

        //we do a flash loan to give us a big gap. from here on out it is cheaper to use normal deleverage. Use Aave for extremely large loans
        if(deficit){
            if(DyDxActive){
                position = position.sub(doDyDxFlashLoan(deficit, position));
            }
            
            // Will decrease number of interactions using aave as backup
            if(position >0 && AaveActive) {
               position = position.sub(doAaveFlashLoan(deficit, position));
            }

            uint8 i = 0;
            //doflashloan should return should equal position unless there was not enough dai to flash loan
            //if we are not in deficit we dont need to do flash loan
            while(position >0){

                require(i < 5, "too many iterations. Try smaller withdraw amount");
                position = position.sub(_normalDeleverage(position));

                i++;

            }
        }
        
        //now withdraw
        //note - this can be optimised by calling in flash loan code
        CErc20I cd = CErc20I(cDAI);
        cd.redeemUnderlying(_amount);

        uint256 _after = want.balanceOf(address(this));
        uint256 _withdrew = _after.sub(_before);
        return _withdrew;
    }
    
    function _loanLogic(bool deficit, uint256 amount, uint256 repayAmount) internal {
        CErc20I cd = CErc20I(cDAI);

        //if in deficit we repay amount and then withdraw
        if(deficit) {
           
            want.safeApprove(cDAI, 0);
            want.safeApprove(cDAI, amount);

            cd.repayBorrow(amount);

            //if we are withdrawing we take more
            cd.redeemUnderlying(repayAmount);
        } else {
            uint amIn = want.balanceOf(address(this));
            want.safeApprove(cDAI, 0);
            want.safeApprove(cDAI, amIn);

            cd.mint(amIn);
           
            cd.borrow(repayAmount);

        }
    }

    // Flash loan DXDY
    function doDyDxFlashLoan(bool deficit, uint256 amountDesired) internal returns (uint256) {
        uint amount = amountDesired;
        ISoloMargin solo = ISoloMargin(SOLO);

        uint256 marketId = _getMarketIdFromTokenAddress(SOLO, address(want));

        // Not enough DAI in DyDx. So we take all we can
        uint amountInSolo = want.balanceOf(SOLO);
  
        if(amountInSolo < amount)
        {
            amount = amountInSolo;
        }

        uint256 repayAmount = _getRepaymentAmountInternal(amount);

        want.safeApprove(SOLO, repayAmount);

        bytes memory data = abi.encode(deficit, amount, repayAmount);


        // 1. Withdraw $
        // 2. Call callFunction(...)
        // 3. Deposit back $
        Actions.ActionArgs[] memory operations = new Actions.ActionArgs[](3);

        operations[0] = _getWithdrawAction(marketId, amount);
        operations[1] = _getCallAction(
            // Encode custom data for callFunction
            data
        );
        operations[2] = _getDepositAction(marketId, repayAmount);

        Account.Info[] memory accountInfos = new Account.Info[](1);
        accountInfos[0] = _getAccountInfo();

        solo.operate(accountInfos, operations);

        emit Leverage(amountDesired, amount, deficit, SOLO);

        return amount;
     }

    function callFunction(
        address sender,
        Account.Info memory account,
        bytes memory data
    ) public override {
        
        (bool deficit, uint256 amount, uint repayAmount) = abi.decode(data,(bool, uint256, uint256));

        _loanLogic(deficit, amount, repayAmount);
    }


    function doAaveFlashLoan (
        bool deficit,
        uint256 _flashBackUpAmount
    )   public returns (uint256 amount)
    {
        //we do not want to do aave flash loans for leveraging up. Fee could put us into liquidation
        if(!deficit){
            return _flashBackUpAmount;
        }

        ILendingPool lendingPool = ILendingPool(addressesProvider.getLendingPool());

        uint256 availableLiquidity = want.balanceOf(address(0x3dfd23A6c5E8BbcFc9581d2E864a68feb6a076d3));

        if(availableLiquidity < _flashBackUpAmount) {
            amount = availableLiquidity;
        }else{
            amount = _flashBackUpAmount;
        }
        
        require(amount <= _flashBackUpAmount, "incorrect amount");

        bytes memory data = abi.encode(deficit, amount);
       
        lendingPool.flashLoan(
                        address(this), 
                        address(want), 
                        amount, 
                        data);

        emit Leverage(_flashBackUpAmount, amount, deficit, AAVE_LENDING);

    }

    function executeOperation(
        address _reserve,
        uint256 _amount,
        uint256 _fee,
        bytes calldata _params
    )
        external
        override
    {
        (bool deficit, uint256 amount) = abi.decode(_params,(bool, uint256));

        _loanLogic(deficit, amount, amount.add(_fee));

        // return the flash loan plus Aave's flash loan fee back to the lending pool
        uint totalDebt = _amount.add(_fee);
        transferFundsBackToPoolInternal(_reserve, totalDebt);
    }

    /*
     * Provide an accurate expected value for the return this strategy
     * would provide to the Vault the next time `report()` is called
     * (since the last time it was called)
     */
    function expectedReturn() public override view returns (uint256){

    }

    /*
     * Provide an accurate estimate for the total amount of assets (principle + return)
     * that this strategy is currently managing, denominated in terms of `want` tokens.
     * This total should be "realizable" e.g. the total value that could *actually* be
     * obtained from this strategy if it were to divest it's entire position based on
     * current on-chain conditions.
     *
     * NOTE: care must be taken in using this function, since it relies on external
     *       systems, which could be manipulated by the attacker to give an inflated
     *       (or reduced) value produced by this function, based on current on-chain
     *       conditions (e.g. this function is possible to influence through flashloan
     *       attacks, oracle manipulations, or other DeFi attack mechanisms).
     *
     * NOTE: It is up to governance to use this function in order to correctly order
     *       this strategy relative to its peers in order to minimize losses for the
     *       Vault based on sudden withdrawals. This value should be higher than the
     *       total debt of the strategy and higher than it's expected value to be "safe".
     */
    function estimatedTotalAssets() public override view returns (uint256){

    }

    /*
     * Perform any strategy unwinding or other calls necessary to capture
     * the "free return" this strategy has generated since the last time it's
     * core position(s) were adusted. Examples include unwrapping extra rewards.
     * This call is only used during "normal operation" of a Strategy, and should
     * be optimized to minimize losses as much as possible. It is okay to report
     * "no returns", however this will affect the credit limit extended to the
     * strategy and reduce it's overall position if lower than expected returns
     * are sustained for long periods of time.
     */
    function prepareReturn() internal override{

    }

    /*
     * Perform any adjustments to the core position(s) of this strategy given
     * what change the Vault made in the "investable capital" available to the
     * strategy. Note that all "free capital" in the strategy after the report
     * was made is available for reinvestment. Also note that this number could
     * be 0, and you should handle that scenario accordingly.
     */
    function adjustPosition() internal override{

    }

    /*
     * Make as much capital as possible "free" for the Vault to take. Some slippage
     * is allowed, since when this method is called the strategist is no longer receiving
     * their performance fee. The goal is for the strategy to divest as quickly as possible
     * while not suffering exorbitant losses. This function is used during emergency exit
     * instead of `prepareReturn()`
     */
    function exitPosition() internal override{

    }

    /*
     * Provide a signal to the keeper that `tend()` should be called. The keeper will provide
     * the estimated gas cost that they would pay to call `tend()`, and this function should
     * use that estimate to make a determination if calling it is "worth it" for the keeper.
     * This is not the only consideration into issuing this trigger, for example if the position
     * would be negatively affected if `tend()` is not called shortly, then this can return `true`
     * even if the keeper might be "at a loss" (keepers are always reimbursed by yEarn)
     *
     * NOTE: this call and `harvestTrigger` should never return `true` at the same time.
     * NOTE: if `tend()` is never intended to be called, it should always return `false`
     */
    function tendTrigger(uint256 gasCost) public override view returns (bool){

    }

    
     /*
     * Provide a signal to the keeper that `harvest()` should be called. The keeper will provide
     * the estimated gas cost that they would pay to call `harvest()`, and this function should
     * use that estimate to make a determination if calling it is "worth it" for the keeper.
     * This is not the only consideration into issuing this trigger, for example if the position
     * would be negatively affected if `harvest()` is not called shortly, then this can return `true`
     * even if the keeper might be "at a loss" (keepers are always reimbursed by yEarn)
     *
     * NOTE: this call and `tendTrigger` should never return `true` at the same time.
     */
    function harvestTrigger(uint256 gasCost) public override view returns (bool){

    }

    function prepareMigration(address _newStrategy) internal override{

    }
   
}