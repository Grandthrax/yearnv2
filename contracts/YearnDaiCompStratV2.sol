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

import "./Interfaces/Chainlink/AggregatorV3Interface.sol";

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

    // Chainlink price feed contracts
    address private constant COMP2USD = 0xdbd020CAeF83eFd542f4De03e3cF0C28A4428bd5;
    address private constant DAI2USD = 0xAed0c38402a5d19df6E4c03F4E2DceD6e29c1ee9;
    address private constant ETH2USD = 0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419;

    // Comptroller address for compound.finance
    ComptrollerI public constant compound = ComptrollerI(0x3d9819210A31b4961b30EF54bE2aeD79B9c9Cd3B); 

    //Only three tokens we use
    address public constant comp =  address(0xc00e94Cb662C3520282E6f5717214004A7f26888);
    CErc20I public constant cDAI = CErc20I(address(0x5d3a536E4D6DbD6114cc1Ead35777bAB948E3643));
    address public constant DAI = address(0x6B175474E89094C44Da98b954EedeAC495271d0F);

    address public constant uniswapRouter = address(0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D);
    address public constant weth = address(0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2); 

    //Operating variables
    uint256 public collateralTarget = 0.73 ether;  // 73% 
    uint256 public blocksToLiquidationDangerZone = 46500;  // 24 hours =  60*60*24*7/13

    uint256 public minDAI = 100 ether; //Only lend if we have enough DAI to be worth it
    uint256 public minCompToSell = 0.5 ether; //used both as the threshold to sell but also as a trigger for harvest
    uint256 public gasFactor = 10; // multiple before triggering harvest

    //To deactivate flash loan provider if needed
    bool public DyDxActive = true;
    bool public AaveActive = true;

    constructor(address _vault) public BaseStrategy(_vault) FlashLoanReceiverBase(AAVE_LENDING)
    {
        //only accept DAI vault
        require(vault.token() == DAI, "!DAI");
                    
        //pre-set approvals
        IERC20(comp).safeApprove(uniswapRouter, uint256(-1));
        want.safeApprove(address(cDAI), uint256(-1));
        want.safeApprove(SOLO, uint256(-1));

    }

    /*
    * Control Functions
    */
    function disableDyDx() external {
        require(msg.sender == governance() || msg.sender == strategist, "!management");// dev: not governance or strategist
        DyDxActive = false;
    }
    function enableDyDx() external {
        require(msg.sender == governance() || msg.sender == strategist, "!management");// dev: not governance or strategist
        DyDxActive = true;
    }
    function disableAave() external {
        require(msg.sender == governance() || msg.sender == strategist, "!management");// dev: not governance or strategist
        AaveActive = false;
    }
    function enableAave() external {
        require(msg.sender == governance() || msg.sender == strategist, "!management");// dev: not governance or strategist
        AaveActive = true;
    }
    function setGasFactor(uint _gasFactor) external {
        require(msg.sender == governance() || msg.sender == strategist, "!management");// dev: not governance or strategist
        gasFactor = _gasFactor;
    }
    function setMinCompToSell(uint _minCompToSell) external {
        require(msg.sender == governance() || msg.sender == strategist, "!management");// dev: not governance or strategist
        minCompToSell = _minCompToSell;
    }
    function setCollateralTarget(uint _collateralTarget) external {
        require(msg.sender == governance() || msg.sender == strategist, "!management");// dev: not governance or strategist
        collateralTarget = _collateralTarget;
    }

    /*
    * Base External Facing Functions 
    */

    /*
     * Expected return this strategy would provide to the Vault the next time `report()` is called
     *
     * The total assets currently in strategy minus what vault believes we have
     * Does not include unrealised profit such as comp.
     */
    function expectedReturn() public override view returns (uint256) {
        uint estimateAssets =  estimatedTotalAssets();

        uint debt = vault.strategies(address(this)).totalDebt;
        if(debt > estimateAssets){
            return 0;
        }else{
            return estimateAssets - debt;
        }
    }

    /*
     * An accurate estimate for the total amount of assets (principle + return)
     * that this strategy is currently managing, denominated in terms of DAI tokens.
     */
    function estimatedTotalAssets() public override view returns (uint256) {
        (uint deposits, uint borrows) = getCurrentPosition();
        
        uint256 _claimableComp = predictCompAccrued();
        uint currentComp = IERC20(comp).balanceOf(address(this));

        // Use chainlink price feed to retrieve COMP and DAI prices expressed in USD. Then convert
        uint256 latestExchangeRate = getLatestExchangeRate();

        uint256 estimatedDAI = latestExchangeRate.mul(_claimableComp.add(currentComp));
        uint256 conservativeDai = estimatedDAI.mul(9).div(10); //10% pessimist
        
        return want.balanceOf(address(this)).add(deposits).add(conservativeDai).sub(borrows);

    }

    /*
     * Aggragate the value in USD for COMP and DAI onchain from different chainlink nodes
     * reducing risk of price manipulation within onchain market.
     * Operation: COMP_PRICE_IN_USD / DAI_PRICE_IN_USD
     */
    function getLatestExchangeRate() public view returns(uint256) {
      ( , uint256 price_comp, , ,  ) = AggregatorV3Interface(COMP2USD).latestRoundData();
      ( , uint256 price_dai, , ,  ) = AggregatorV3Interface(DAI2USD).latestRoundData();
      
      return price_comp.mul(1 ether).div(price_dai).div(1 ether);
    }

    function getCompValInWei(uint256 _amount) public view returns(uint256) {
      ( , uint256 price_comp, , ,  ) = AggregatorV3Interface(COMP2USD).latestRoundData();
      ( , uint256 price_eth, , ,  ) = AggregatorV3Interface(ETH2USD).latestRoundData();
      
      return price_comp.mul(1 ether).div(price_eth).mul(_amount).div(1 ether);
    }

    /*
     * Provide a signal to the keeper that `tend()` should be called. 
     * (keepers are always reimbursed by yEarn)
     *
     * NOTE: this call and `harvestTrigger` should never return `true` at the same time.
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
     * Provide a signal to the keeper that `harvest()` should be called.
     * gasCost is expected_gas_use * gas_price 
     * (keepers are always reimbursed by yEarn)
     *
     * NOTE: this call and `tendTrigger` should never return `true` at the same time.
     */
    function harvestTrigger(uint256 gasCost) public override view returns (bool) {

        if(vault.creditAvailable() > minDAI)
        {
            return true;
        }

        // after enough comp has accrued we want the bot to run
        uint256 _claimableComp = predictCompAccrued();

        if(_claimableComp > minCompToSell) {
            // check value of COMP in wei
            uint256 _compWei = getCompValInWei(_claimableComp.add(IERC20(comp).balanceOf(address(this))));
            if(_compWei > gasCost.mul(gasFactor)) {
                return true;
            }
        }
       
        return false;
    }


    /*****************
    * Public non-base function
    ******************/

    //Calculate how many blocks until we are in liquidation based on current interest rates
    //WARNING does not include compounding so the estimate becomes more innacurate the further ahead we look
    //equation. Compound doesn't include compounding for most blocks
    //((deposits*colateralThreshold - borrows) / (borrows*borrowrate - deposits*colateralThreshold*interestrate));
    function getblocksUntilLiquidation() public view returns (uint256 blocks){
        
        (, uint collateralFactorMantissa,) = compound.markets(address(cDAI));
        
        (uint deposits, uint borrows) = getCurrentPosition();

        uint borrrowRate = cDAI.borrowRatePerBlock();

        uint supplyRate = cDAI.supplyRatePerBlock();

        uint collateralisedDeposit1 = deposits.mul(collateralFactorMantissa);
        uint collateralisedDeposit = collateralisedDeposit1.div(1e18);

        uint denom1 = borrows.mul(borrrowRate);
        uint denom2 =  collateralisedDeposit.mul(supplyRate);
      
        if(denom2 >= denom1 ){
            blocks = uint256(-1);
        }else{
            uint numer = collateralisedDeposit.sub(borrows);
            uint denom = denom1 - denom2;

            blocks = numer.mul(1e18).div(denom);
        }
    }

    // This function makes a prediction on how much comp is accrued
    // It is not 100% accurate as it uses current balances in Compound to predict into the past
    function predictCompAccrued() public view returns (uint) {
        
        (uint256 deposits, uint256 borrows) = getCurrentPosition();
        if(deposits == 0){
            return 0; // should be impossible to have 0 balance and positive comp accrued
        }
        
        //comp speed is amount to borrow or deposit (so half the total distribution for dai)
        uint256 distributionPerBlock = compound.compSpeeds(address(cDAI));

        uint256 totalBorrow = cDAI.totalBorrows();

        //total supply needs to be echanged to underlying using exchange rate
        uint256 totalSupplyCtoken = cDAI.totalSupply();
        uint256 totalSupply = totalSupplyCtoken.mul(cDAI.exchangeRateStored()).div(1e18);

        uint256 blockShareSupply = deposits.mul(distributionPerBlock).div(totalSupply);
        uint256 blockShareBorrow = borrows.mul(distributionPerBlock).div(totalBorrow);

        //how much we expect to earn per block
        uint256 blockShare = blockShareSupply.add(blockShareBorrow);
      
        //last time we ran harvest
        uint256 lastReport = vault.strategies(address(this)).lastSync;
        return (block.number.sub(lastReport)).mul(blockShare);
    }
    
    //Returns the current position
    //WARNING - this returns just the balance at last time someone touched the cDAI token. Does not accrue interst in between
    //cDAI is very active so not normally an issue.
    function getCurrentPosition() public view returns (uint deposits, uint borrows) {

        (, uint ctokenBalance, uint borrowBalance, uint exchangeRate) = cDAI.getAccountSnapshot(address(this));
        borrows = borrowBalance;

        deposits =  ctokenBalance.mul(exchangeRate).div(1e18);
    }

    //statechanging version
    function getLivePosition() public returns (uint deposits, uint borrows) {
        deposits = cDAI.balanceOfUnderlying(address(this));

        //we can use non state changing now because we updated state with balanceOfUnderlying call
        borrows = cDAI.borrowBalanceStored(address(this));
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
     * A core method. 
     * Called at beggining of harvest before providing report to owner
     * 1 - claim accrued comp
     * 2 - if enough to be worth it we sell
     * 3 - because we lose money on our loans we need to offset profit from comp. 
     */ 
    function prepareReturn() internal override {
        if(cDAI.balanceOf(address(this)) == 0){
            //no position to harvest
            return;
        }

        //claim comp accrued
        _claimComp();
        //sell comp
        _disposeOfComp();

        uint balance = estimatedTotalAssets();
        uint daiBalance = want.balanceOf(address(this));
        
        uint debt = vault.strategies(address(this)).totalDebt;

        //Balance - Total Debt is profit
        if(balance > debt){
             uint profit = balance- debt;
            
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
     * Second core function. Happens after report call.
     *
     * Similar to deposit function from V1 strategy
     */

    function adjustPosition() internal override {

        //emergency exit is dealt with in prepareReturn
        if(emergencyExit){
            return;
        }

        if(reserve != 0){
            //reset reserve so it doesnt interfere anywhere else
            reserve = 0;
        }

        //we are spending all our cash unless we have an outstanding debt (when we wont have any cash)
        uint _wantBal = want.balanceOf(address(this));
        if(outstanding > _wantBal){
            //withdrawn the money we need. False so we dont use backup and pay aave fees for mature deleverage
            _withdrawSome(outstanding - _wantBal, false);

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
                if(position > IERC20(DAI).balanceOf(SOLO)){
                    position = position.sub(_noFlashLoan(position, deficit));
                }
           
                //flash loan to position 
                doDyDxFlashLoan(deficit, position);
            }
        }
    }

    /*************
    * Very important function
    * Input: amount we want to withdraw and whether we are happy to pay extra for Aave. 
    *       cannot be more than we 
    * Returns amount we were able to withdraw. notall if user has some balance left
    *
    * Deleverage position -> redeem our cTokens
    ******************** */
    function _withdrawSome(uint256 _amount, bool _useBackup) internal returns (bool notAll) {

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
                    notAll= false;
                    break;
               }
            }
        }
        
        //now withdraw
        //if we want too much we just take max

        //This part makes sure our withdrawal does not force us into liquidation        
        (uint depositBalance ,uint borrowBalance) = getCurrentPosition();
        uint AmountNeeded = borrowBalance.mul(1e18).div(collateralTarget);
        if(depositBalance.sub(AmountNeeded) < _amount){
            cDAI.redeemUnderlying(depositBalance.sub(AmountNeeded));
        }else{
            cDAI.redeemUnderlying(_amount);
        }

        //let's sell some comp if we have more than needed
        //flash loan would have sent us comp if we had some accrued so we don't need to call claim comp
        _disposeOfComp();
    }

    /***********
    *  This is the main logic for calculating how to change our lends and borrows
    *  Input: balance. The net amount we are going to deposit/withdraw.
    *  Input: dep. Is it a deposit or withdrawal
    *  Output: position. The amount we want to change our current borrow position.                   
    *  Output: deficit. True if we are reducing position size
    *
    *  For instance deficit =false, position 100 means increase borrowed balance by 100
    ****** */
    function _calculateDesiredPosition(uint256 balance, bool dep) internal returns (uint256 position, bool deficit) {

        //we want to use statechanging for safety
        (uint deposits, uint borrows) = getLivePosition();

        //When we unwind we end up with the difference between borrow and supply
        uint unwoundDeposit = deposits.sub(borrows);

        //we want to see how close to collateral target we are. 
        //So we take our unwound deposits and add or remove the balance we are are adding/removing.
        //This gives us our desired future undwoundDeposit (desired supply)

        uint desiredSupply = 0;
        if(dep){
            desiredSupply = unwoundDeposit.add(balance);
        }else{
            desiredSupply = unwoundDeposit.sub(balance);            
        }

        //(ds *c)/(1-c)
        uint num = desiredSupply.mul(collateralTarget);
        uint den = uint256(1e18).sub(collateralTarget);

        uint desiredBorrow = num.div(den);
        if(desiredBorrow > 1e18 ){
            //stop us going right up to the wire
            desiredBorrow = desiredBorrow - 1e18;
        }

        //now we see if we want to add or remove balance
        // if the desired borrow is less than our current borrow we are in deficit. so we want to reduce position
        if(desiredBorrow < borrows){
            deficit = true;
            position = borrows - desiredBorrow; //safemath check done in if statement

        }else{
            //otherwise we want to increase position
            deficit = false;
            position = desiredBorrow - borrows;
        }
    }

    /*
     * Liquidate as many assets as possible to `want`, irregardless of slippage,
     * up to `_amount`. Any excess should be re-invested here as well.
     */
    function liquidatePosition(uint256 _amount) internal override {
        
        if(netBalanceLent() <= _amount){
            //if we cant afford to withdraw we take all we can
            //withdraw all we can
            exitPosition();
        }else{
            uint256 _balance = want.balanceOf(address(this));

            if (_balance < _amount) {
                require(!_withdrawSome(_amount.sub(_balance), true), "DelevFirst");
            }
        }
    }

     function _claimComp() internal {
      
        CTokenI[] memory tokens = new CTokenI[](1);
        tokens[0] =  cDAI;

        compound.claimComp(address(this), tokens);
    }

    //sell comp function
    function _disposeOfComp() internal {

        uint256 _comp = IERC20(comp).balanceOf(address(this));
        
        if (_comp > minCompToSell) {

            address[] memory path = new address[](3);
            path[0] = comp;
            path[1] = weth;
            path[2] = DAI;

            IUniswapV2Router02(uniswapRouter).swapExactTokensForTokens(_comp, uint256(0), path, address(this), now);
        }
    }

    /*
     * Make as much capital as possible "free" for the Vault to take. Some slippage
     * is allowed. 
     */
    function exitPosition() internal override {

        //we dont use getCurrentPosition() because it won't be exact
         (uint deposits, uint borrows) = getLivePosition();
        _withdrawSome(deposits.sub(borrows), true);

    }

    //lets leave
    function prepareMigration(address _newStrategy) internal override{
        exitPosition();
       
        (, , uint borrowBalance,) = cDAI.getAccountSnapshot(address(this));

        require(borrowBalance ==0, "DELEVERAGE_FIRST");

        want.safeTransfer(_newStrategy, want.balanceOf(address(this)));

        cDAI.transfer(_newStrategy, cDAI.balanceOf(address(this)));
        
        IERC20 _comp = IERC20(comp);
        _comp.safeTransfer(_newStrategy, _comp.balanceOf(address(this)));

    }

    //Three functions covering normal leverage and deleverage situations
    // max is the max amount we want to increase our borrowed balance
    // returns the amount we actually did
    function _noFlashLoan(uint256 max, bool deficit) internal returns (uint256 amount){

        //we can use non-state changing because this function is always called after _calculateDesiredPosition
        (uint lent, uint borrowed) = getCurrentPosition();
       
        if(borrowed == 0){
             return 0;
         }

        (, uint collateralFactorMantissa,) = compound.markets(address(cDAI));

        if(deficit){
           amount = _normalDeleverage(max, lent, borrowed, collateralFactorMantissa);
        }else{
           amount = _normalLeverage(max, lent, borrowed, collateralFactorMantissa);
        }

        emit Leverage(max, amount, deficit,  address(0));
    }

    //maxDeleverage is how much we want to reduce by
    function _normalDeleverage(uint256 maxDeleverage, uint lent, uint borrowed, uint collatRatio) internal returns (uint256 deleveragedAmount) {

        uint theoreticalLent = borrowed.mul(1e18).div(collatRatio);

        deleveragedAmount = lent.sub(theoreticalLent);
        
        if(deleveragedAmount >= borrowed){
            deleveragedAmount = borrowed;
        }
        if(deleveragedAmount >= maxDeleverage){
            deleveragedAmount = maxDeleverage;
        }

        cDAI.redeemUnderlying(deleveragedAmount);
        
        //our borrow has been increased by no more than maxDeleverage
        cDAI.repayBorrow(deleveragedAmount);
    }

    //maxDeleverage is how much we want to increase by
    function _normalLeverage(uint256 maxLeverage, uint lent, uint borrowed, uint collatRatio) internal returns (uint256 leveragedAmount){

        uint theoreticalBorrow = lent.mul(collatRatio).div(1e18);

        leveragedAmount = theoreticalBorrow.sub(borrowed);

        if(leveragedAmount >= maxLeverage){
            leveragedAmount = maxLeverage;
        }

        cDAI.borrow(leveragedAmount);
        cDAI.mint(want.balanceOf(address(this)));

    }

    //called by flash loan
    function _loanLogic(bool deficit, uint256 amount, uint256 repayAmount) internal {
        //if in deficit we repay amount and then withdraw
        if(deficit) {
           

            cDAI.repayBorrow(amount);

            //if we are withdrawing we take more to cover fee
            cDAI.redeemUnderlying(repayAmount);
        } else {   
      
            require(cDAI.mint(want.balanceOf(address(this))) == 0, "mint error");

            //borrow more to cover fee
            // fee is so low for dydx that it does not effect our liquidation risk. 
            //DONT USE FOR AAVE
            cDAI.borrow(repayAmount);

        }
    }

   function protectedTokens() internal override view returns (address[] memory) {
        address[] memory protected = new address[](3);
        protected[0] = address(want);
        protected[1] = comp;
        protected[2] = address(cDAI);
        return protected;
    }

    /******************
    * Flash loan stuff
    ****************/

    // Flash loan DXDY
    // amount desired is how much we are willing for position to change
    function doDyDxFlashLoan(bool deficit, uint256 amountDesired) internal returns (uint256) {
        uint borrowbefore = cDAI.borrowBalanceCurrent(address(this));

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

    //returns our current collateralisation ratio. Should be compared with collateralTarget
     function storedCollateralisation() public view returns (uint256 collat){
          ( uint256 lend, uint256 borrow) = getCurrentPosition();
        if(lend == 0){
            return 0;
        }
         collat = uint(1e18).mul(borrow).div(lend);
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
        
        require(amount <= _flashBackUpAmount); // dev: "incorrect amount"

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
