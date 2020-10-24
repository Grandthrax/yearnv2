pragma solidity ^0.6.9;
pragma experimental ABIEncoderV2;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/math/SafeMath.sol";

import "./Interfaces/Compound/CErc20I.sol";
import "./Interfaces/Compound/ComptrollerI.sol";

import "./Interfaces/UniswapInterfaces/IUniswapV2Router02.sol";

import "./Interfaces/Yearn/IController.sol";

import "./Interfaces/DyDx/DydxFlashLoanBase.sol";
import "./Interfaces/DyDx/ICallee.sol";

import "./Interfaces/Aave/FlashLoanReceiverBase.sol";
import "./Interfaces/Aave/ILendingPoolAddressesProvider.sol";
import "./Interfaces/Aave/ILendingPool.sol";

import "./BaseStrategy.sol";

/********************
*   A simple Comp farming strategy from leveraged lending of DAI. 
*   Uses Flash Loan to leverage up quicker. But not neccessary for operation
*   https://github.com/Grandthrax/yearnv2/blob/master/contracts/YearnDaiCompStratV2.sol
*
********************* */

contract YearnDaiCompStratV2 is BaseStrategy, DydxFlashloanBase, ICallee, FlashLoanReceiverBase {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;
    
    // @notice emitted when trying to do Flash Loan. flashLoan address is 0x00 when no flash loan used
    event Leverage(uint amountRequested, uint amountGiven, bool deficit, address flashLoan);

    //Flash Loan Providers
    address private constant SOLO = 0x1E0447b19BB6EcFdAe1e4AE1694b0C3659614e4e;
    address private constant AAVE_LENDING = 0x24a42fD28C976A61Df5D00D0599C34c4f90748c8;

    // Comptroller address for compound.finance
    ComptrollerI public constant compound = ComptrollerI(0x3d9819210A31b4961b30EF54bE2aeD79B9c9Cd3B); 

    //Only three tokens we use
    address public constant comp = address(0xc00e94Cb662C3520282E6f5717214004A7f26888);
    address public constant cDAI = address(0x5d3a536E4D6DbD6114cc1Ead35777bAB948E3643);
    address public constant DAI = address(0x6B175474E89094C44Da98b954EedeAC495271d0F);

    // used for comp <> weth <> dai route
    address public constant uniswapRouter = address(0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D);
    address public constant weth = address(0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2); 

    //Operating variables
    uint256 public collateralTarget = 0.73 ether;  // 73% 
    uint256 public blocksToLiquidationDangerZone = 6650;  // 24 hours =  60*60*24/13


    uint256 public minDAI = 100 ether; //lending and borrowing is expensive. Only do if we have enough DAI to be worth it
    uint256 public minCompToSell = 0.1 ether; //used both as the threshold to sell but also as a trigger for harvest

    //To deactivate flash loan provider if needed
    bool public DyDxActive = true;
    bool public AaveActive = true;

    constructor(address _vault) public BaseStrategy(_vault) FlashLoanReceiverBase(AAVE_LENDING)
    {
        //only accept DAI vault
        require(vault.token() == DAI, "!DAI");
    }

    /*
    * Control Functions
    */
    function disableDyDx() external {
        require(msg.sender == governance() || msg.sender == strategist, "not governance or strategist");
        DyDxActive = false;
    }
    function enableDyDx() external {
        require(msg.sender == governance() || msg.sender == strategist, "not governance or strategist");
        DyDxActive = true;
    }
    function disableAave() external {
        require(msg.sender == governance() || msg.sender == strategist, "not governance or strategist");
        AaveActive = false;
    }
    function enableAave() external {
        require(msg.sender == governance() || msg.sender == strategist, "not governance or strategist");
        AaveActive = true;
    }

    /*
    * Base External Facing Functions 
    */

    /*
     * Provide an accurate expected value for the return this strategy
     * would provide to the Vault the next time `report()` is called
     * (since the last time it was called)
     *
     * In other words - the total assets currently in strategy minus what vault believes we have
     * Does not include unrealised profit such as comp.
     */
    function expectedReturn() public override view returns (uint256) {
        uint estimateAssets =  estimatedTotalAssets();
        uint debt = vault.strategies(address(this)).totalDebt;
        if(debt > estimateAssets){
            return 0;
        }else{
            return estimateAssets.sub(debt);
        }

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
     *
     */
    function estimatedTotalAssets() public override view returns (uint256) {
         (uint deposits, uint borrows) =getCurrentPosition();
        return want.balanceOf(address(this)).add(deposits).sub(borrows);

        //We do not include comp predicted price conversion because it is could be manipulated
        //Maybe we can use the average of last day or something...
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
    function tendTrigger(uint256 gasCost) public override view returns (bool) {
        if(harvestTrigger(0)){
            //harvest takes priority
            return false;
        }

        if(getblocksUntilLiquidation() <= blocksToLiquidationDangerZone){
                return true;
        }
        
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
    function harvestTrigger(uint256 gasCost) public override view returns (bool) {

        if(vault.creditAvailable() > minDAI)
        {
            return true;
        }

        // after enough comp has accrued we want the bot to run
        // future extension could be checking value of comp and comparing to gas
        if(_predictCompAccrued() > minCompToSell){
            return true;
        }
       
        return false;
    }


    /*****************
    * Public non-base function
    ******************/

    //Calculate how many blocks until we are in liquidation based on current interest rates
    //WARNING does not include compounding so the estimate becomes more innacurate the further ahead we look
    //equation. Compound doesn't include compounding for most blocks so it is more accurate than you'd think
    //((deposits*colateralThreshold - borrows) / (borrows*borrowrate - deposits*colateralThreshold*interestrate));
    function getblocksUntilLiquidation() public view returns (uint256 blocks){

        
        (, uint collateralFactorMantissa,) = compound.markets(cDAI);
        
        (uint deposits, uint borrows) = getCurrentPosition();
        CErc20I cd =CErc20I(cDAI);
        uint borrrowRate = cd.borrowRatePerBlock();

        uint supplyRate = cd.supplyRatePerBlock();

        uint collateralisedDeposit1 = deposits.mul(collateralFactorMantissa);
        uint collateralisedDeposit = collateralisedDeposit1.div(1e18);

        uint denom1 = borrows.mul(borrrowRate);
        uint denom2 =  collateralisedDeposit.mul(supplyRate);
      
        //we should never be in liquidation
        if(denom2 >= denom1 ){
            blocks = uint256(-1);
        }else{
            uint numer = collateralisedDeposit.sub(borrows);
            uint denom = denom1.sub(denom2);

            blocks = numer.mul(1e18).div(denom);
        }
    }

    // This function makes a prediction on how much comp is accrued
    // It is not 100% accurate as it uses current balances in Compound to predict into the past
    // A completey accurate number requires state changing calls
    function _predictCompAccrued() internal view returns (uint){
        
        (uint256 deposits, uint256 borrows) = getCurrentPosition();
        if(deposits == 0){
            return 0; // should be impossible to have 0 balance and positive comp accrued
        }

        //how much comp is being rewarded per block to DAI lenders and borrowers
        //comp speed is amount to borrow or deposit (so half the total distribution for dai)
        uint256 distributionPerBlock = compound.compSpeeds(cDAI);

        CErc20I cd = CErc20I(cDAI);
        uint256 totalBorrow = cd.totalBorrows();

        //total supply needs to be echanged to underlying
        uint256 totalSupplyCtoken = cd.totalSupply();
        uint256 totalSupply = totalSupplyCtoken.mul(cd.exchangeRateStored()).div(1e18);

        uint256 blockShareSupply = deposits.mul(distributionPerBlock).div(totalSupply);
        uint256 blockShareBorrow = borrows.mul(distributionPerBlock).div(totalBorrow);

        //how much we expect to earn per block
        uint256 blockShare = blockShareSupply.add(blockShareBorrow);
      //  uint256 blockShare = (deposits.add(borrows)).mul(distributionPerBlock).div((totalBorrow.add(totalSupply)));

        //last time we ran harvest
       
        uint256 lastReport = vault.strategies(address(this)).lastSync;
        return (block.number.sub(lastReport)).mul(blockShare);

    }
    
    //Returns the current position
    //WARNING - this returns just the balance at last time someone touched the cDAI token. Does not accrue interst inbetween
    //cDAI is very active so not normally an issue. Shows up more in testing than production
    function getCurrentPosition() public view returns (uint deposits, uint borrows) {
        CErc20I cd = CErc20I(cDAI);
       
        (, uint ctokenBalance, uint borrowBalance, uint exchangeRate) = cd.getAccountSnapshot(address(this));
        borrows = borrowBalance;

        deposits =  ctokenBalance.mul(exchangeRate).div(1e18);
    }

    //Same warning as above
    function netBalanceLent() public view returns (uint256) {
        (uint deposits, uint borrows) =getCurrentPosition();
        return deposits.sub(borrows);
    }


    /***********
    * internal core logic
    *********** */
    
    /*
     * Perform any strategy unwinding or other calls necessary to capture
     * the "free return" this strategy has generated since the last time it's
     * core position(s) were adusted. Examples include unwrapping extra rewards.
     * This call is only used during "normal operation" of a Strategy, and should
     * be optimized to minimize losses as much as possible. It is okay to report
     * "no returns", however this will affect the credit limit extended to the
     * strategy and reduce it's overall position if lower than expected returns
     * are sustained for long periods of time.
     *
     * A core method. 
     * 1 - claim accrued comp
     * 2 - if enough to be worth it we sell
     * 3 - because we lose money on our loans we need to offset profit from comp. 
     */ 
    function prepareReturn() internal override {
        if(CTokenI(cDAI).balanceOf(address(this)) == 0){
            //no position to harvest
            return;
        }

        //claim comp accrued
        _claimComp();
        //sell comp
        _disposeOfComp();

        uint balance = estimatedTotalAssets();
        uint daiBalance = want.balanceOf(address(this));

        StrategyParams memory params= vault.strategies(address(this));
        uint debt = params.totalDebt;

        //Balance - Total Debt is profit
        if(balance > debt){
             uint profit = balance.sub(debt);
            
            if(profit >= daiBalance ){
                //all reserve is profit
                reserve = 0;
            }else{

                //some dai is not profit and needs to pay off our interest
                //this is most likely situation
                reserve = daiBalance.sub(profit);
            }
        } else{
            //no profit so we set our reserves to our total balance
            reserve = daiBalance;
        }  
    }

    /*
     * Perform any adjustments to the core position(s) of this strategy given
     * what change the Vault made in the "investable capital" available to the
     * strategy. Note that all "free capital" in the strategy after the report
     * was made is available for reinvestment. Also note that this number could
     * be 0, and you should handle that scenario accordingly.
     *
     * Similar to deposit function from V1 strategy
     *
     */

    function adjustPosition() internal override {

        //if emergency exit is true then we have already exited as much as possible in first part of harvest
        if(emergencyExit){
            return;
        }

        //we are spending all our cash unless we have an outstanding debt (when we wont have any cash)
        uint _wantBal = want.balanceOf(address(this));
        if(outstanding > _wantBal){

            //withdrawn the money we need
            _withdrawSome(outstanding.sub(_wantBal), false);

            return;
        }

        // We pass in the balance we are adding. 
        // We get returned the amount we need to reduce or add to our loan positions to keep at our target collateral ratio
        (uint256 position, bool deficit) = _calculateDesiredPosition(_wantBal, true);
        
        //if we are below minimun DAI change it is not worth doing        
        if (position > minDAI) {

            //if dydx is not active we just try our best with basic leverage
            if(!DyDxActive){
                _noFlashLoan(position, deficit);
            }else{
                //if there is huge position to improve we want to do normal leverage. it is quicker
                if(position > IERC20(DAI).balanceOf(SOLO) && !deficit){
                    position = position.sub(_noFlashLoan(position, deficit));
                }
           
                //flash loan to position 
                doDyDxFlashLoan(deficit, position);
            }
        }
    }

    /*************
    * Very important function
    * Input: amount we want to withdraw and whether we are happy to pay extra for Aave
    * Returns amount we were able to withdraw
    *
    * Deleverage position -> redeem our cTokens
    ******************** */
    function _withdrawSome(uint256 _amount, bool _useBackup) internal returns (uint256) {

        (uint256 position, bool deficit) = _calculateDesiredPosition(_amount, false);

        //We see how much we withdrew by doing a snapshot now and at end
        uint256 _before = want.balanceOf(address(this));

        //If there is no deficit we dont need to adjust position
        if(deficit){

            //we do a flash loan to give us a big gap. from here on out it is cheaper to use normal deleverage. Use Aave for extremely large loans
            if(DyDxActive){
                position = position.sub(doDyDxFlashLoan(deficit, position));
            }
            
            // Will decrease number of interactions using aave as backup
            // because of fee we only use in emergency
            if(position >0 && AaveActive && _useBackup) {
               position = position.sub(doAaveFlashLoan(deficit, position));
            }

            uint8 i = 0;
            //position will equal 0 unless we haven't been able to deleverage enough with flash loan
            //if we are not in deficit we dont need to do flash loan
            while(position >0){

                position = position.sub(_noFlashLoan(position, true));
                i++;

                //A limit set so we don't run out of gas
                if(i >= 5){
                   break;
               }
            }
        }
        
        //now withdraw
        //if we want too much we just take max
        CErc20I cd = CErc20I(cDAI);

        //This part makes sure our withdrawal does not force us into liquidation        
        (uint depositBalance ,uint borrowBalance) = getCurrentPosition();
        uint AmountNeeded = borrowBalance.mul(1e18).div(collateralTarget);
        if(depositBalance.sub(AmountNeeded) < _amount){
            cd.redeemUnderlying(depositBalance.sub(AmountNeeded));
        }else{
            cd.redeemUnderlying(_amount);
        }

        //let's sell some comp if we have more than needed
        //flash loan would have sent us comp if we had some accrued so we don't need to call claim comp
        _disposeOfComp();

        uint256 _after = want.balanceOf(address(this));
        uint256 _withdrew = _after.sub(_before);
        return _withdrew;
    }

    /***********
    *  This is the main logic for calculating how to change our lends and borrows
    *  Input: balance. The net amount we are going to deposit/withdraw.
    *  Input: dep. Is it a deposit or withdrawal
    *  Output: position. The amount we want to change our current position. 
    *  Output: deficit. True if we are reducing position size
    *
    ****** */
    // This is the main function works out what we want to change with our flash loan
    // . and dep is whether is this a deposit or withdrawal  
    //returns our position change      
    function _calculateDesiredPosition(uint256 balance, bool dep) internal view returns (uint256 position, bool deficit) {
        (uint256 deposits, uint256 borrows) = getCurrentPosition();

        //When we unwind we end up with the difference between borrow and supply
        uint unwoundDeposit = deposits.sub(borrows);

        //we want to see how close to collateral target we are. 
        //So we take our unwound deposits and add or remove the balance we are are adding/removing.
        //This gives us our desired future undwoundDeposit (desired supply)

        uint desiredSupply = 0;
        if(dep){
            desiredSupply = unwoundDeposit.add(balance);
        }else{
            require(unwoundDeposit >= balance, "withdrawing more than balance");
            desiredSupply = unwoundDeposit.sub(balance);
        }

        //desired borrow is (leveraged targed-1)xbalance. So if we want 4x leverage (max allowed). we want to borrow 3x desired balance
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

    /*
     * Liquidate as many assets as possible to `want`, irregardless of slippage,
     * up to `_amount`. Any excess should be re-invested here as well.
     */
    function liquidatePosition(uint256 _amount) internal override {
        
        if(estimatedTotalAssets() <= _amount){
            //if we cant afford to withdraw we take all we can
            //withdraw all we can
            exitPosition();
        }else{
            uint256 _balance = want.balanceOf(address(this));

            if (_balance < _amount) {
                _withdrawSome(_amount.sub(_balance), true);
            }
        }
    }

     function _claimComp() public {
      
        CTokenI[] memory tokens = new CTokenI[](1);
        tokens[0] =  CTokenI(cDAI);

        compound.claimComp(address(this), tokens);
    }

    function _disposeOfComp() internal {

        uint256 _comp = IERC20(comp).balanceOf(address(this));
        
        if (_comp > minCompToSell) {

            //for safety we set approval to 0 and then reset to required amount
            IERC20(comp).safeApprove(uniswapRouter, 0);
            IERC20(comp).safeApprove(uniswapRouter, _comp);

            address[] memory path = new address[](3);
            path[0] = comp;
            path[1] = weth;
            path[2] = DAI;

            IUniswapV2Router02(uniswapRouter).swapExactTokensForTokens(_comp, uint256(0), path, address(this), now.add(1800));

        }
    }


    /*
     * Make as much capital as possible "free" for the Vault to take. Some slippage
     * is allowed, since when this method is called the strategist is no longer receiving
     * their performance fee. The goal is for the strategy to divest as quickly as possible
     * while not suffering exorbitant losses. This function is used during emergency exit
     * instead of `prepareReturn()`
     */
    function exitPosition() internal override {

        CErc20I cd = CErc20I(cDAI);
        //we dont use getCurrentPosition() because it won't be exact
        uint lent = cd.balanceOfUnderlying(address(this));
        uint borrowed = cd.borrowBalanceCurrent(address(this));
        _withdrawSome(lent.sub(borrowed), true);

    }

    //lets leave
    function prepareMigration(address _newStrategy) internal override{
        exitPosition();

         CErc20I cd = CErc20I(cDAI);
       
        (, , uint borrowBalance,) = cd.getAccountSnapshot(address(this));

        require(borrowBalance ==0, "not ready to migrate. deleverage first");

        want.safeTransfer(_newStrategy, want.balanceOf(address(this)));

        cd.transfer(_newStrategy, cd.balanceOf(address(this)));

    }




    //Three functions covering normal leverage and deleverage situations
    function _noFlashLoan(uint256 max, bool deficit) internal returns (uint256 amount){
        CErc20I cd =CErc20I(cDAI);
        uint lent = cd.balanceOfUnderlying(address(this));

        //we can use stored because interest was accrued in last line
        uint borrowed = cd.borrowBalanceStored(address(this));
        if(borrowed == 0){
             return 0;
         }

        (, uint collateralFactorMantissa,) = compound.markets(cDAI);

        if(deficit){
           amount = _normalDeleverage(max, lent, borrowed, collateralFactorMantissa);
        }else{
            _normalLeverage(max, lent, borrowed, collateralFactorMantissa);
        }

        emit Leverage(max, amount, deficit,  address(0));
    }

        //maxDeleverage is how much we want to reduce by
    function _normalDeleverage(uint256 maxDeleverage, uint lent, uint borrowed, uint collatRatio) internal returns (uint256 deleveragedAmount) {
        
        CErc20I cd =CErc20I(cDAI);
        uint theoreticalLent = borrowed.mul(1e18).div(collatRatio);

        deleveragedAmount = lent.sub(theoreticalLent);
        
        if(deleveragedAmount >= borrowed){
            deleveragedAmount = borrowed;
        }
        if(deleveragedAmount >= maxDeleverage){
            deleveragedAmount = maxDeleverage;
        }
        _Down(deleveragedAmount, deleveragedAmount);
    }

    //maxDeleverage is how much we want to reduce by
    function _normalLeverage(uint256 maxLeverage, uint lent, uint borrowed, uint collatRatio) internal returns (uint256 leveragedAmount){

        CErc20I cd =CErc20I(cDAI);

        uint theoreticalBorrow = lent.mul(collatRatio).div(1e18);

        leveragedAmount = theoreticalBorrow.sub(borrowed);

        if(leveragedAmount >= maxLeverage){
            leveragedAmount = maxLeverage;
        }

        _Up(leveragedAmount, leveragedAmount);

    }

    //Three functions covering different leverage situations
    function _Up(uint borrow, uint mint) internal {
        CErc20I cd =CErc20I(cDAI);

        cd.borrow(borrow);

        IERC20 _want = IERC20(want);
        _want.safeApprove(cDAI, 0);
        _want.safeApprove(cDAI, mint);
        cd.mint(mint);
    }
    function _Down(uint redeem, uint repay) internal {
        CErc20I cd =CErc20I(cDAI);

        cd.redeemUnderlying(redeem);
        
        want.safeApprove(cDAI, 0);
        want.safeApprove(cDAI, repay);
        cd.repayBorrow(repay);
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


    //needs to be overriden but can't do currently
    /*
   function protectedTokens() internal override view returns (address[] memory) {
        address[] memory protected = new address[](2);
        protected[0] = address(want);
        protected[1] = comp;
        return protected;
    }*/


    /******************
    * Flash loan stuff
    ****************/

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

    //DyDx calls this function after doing flash loan
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

    //Aave calls this function after doing flash loan
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

   
}
