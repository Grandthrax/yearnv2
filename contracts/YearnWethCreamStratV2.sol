pragma solidity ^0.6.12;
pragma experimental ABIEncoderV2;

import "@openzeppelinV3/contracts/token/ERC20/IERC20.sol";
import "@openzeppelinV3/contracts/math/SafeMath.sol";
import "@openzeppelinV3/contracts/token/ERC20/SafeERC20.sol";

//cream is fork of compound and has same interface
import "./Interfaces/Compound/CEtherI.sol";

import "./Interfaces/UniswapInterfaces/IWETH.sol";

import "./Interfaces/Yearn/IController.sol";

import "./BaseStrategy.sol";


/********************
 *   An ETH Cream strategy with a liquidity buffer to ensure we don't end up in crisis.
 *   Made by SamPriestley.com
 *   https://github.com/Grandthrax/yearnv2/blob/master/contracts/YearnWethCreamStratV2.sol
 *
 ********************* */

contract YearnWethCreamStratV2 is BaseStrategy {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    string public constant name = "YearnWethCreamStratV2";

    //Only three tokens we use
    CEtherI public constant crETH = CEtherI(address(0xD06527D5e56A3495252A528C4987003b712860eE));

    IWETH public constant weth = IWETH(address(0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2));

    uint256 public maxReportDelay = 50; //6300 is once a day. lower vaule used for testing

    //Operating variables
    uint256 public liquidityCushion = 3000 ether; // 3000 ether ~ 1m usd

    uint256 public profitFactor = 50; // multiple before triggering harvest
    uint256 public dustThreshold = 0.01 ether; // multiple before triggering harvest


    constructor(address _vault) public BaseStrategy(_vault) {
        //only accept ETH vault
        require(vault.token() == address(weth), "!WETH");
    }

    //to receive eth from weth
    receive() external payable {}

    /*
     * Control Functions
     */
    function setProfitFactor(uint256 _profitFactor) external {
        require(msg.sender == governance() || msg.sender == strategist, "!management"); // dev: not governance or strategist
        profitFactor = _profitFactor;
    }

    /*
     * Base External Facing Functions
     */

    /*
     * Expected return this strategy would provide to the Vault the next time `report()` is called
     *
     * The total assets currently in strategy minus what vault believes we have
     */
    function expectedReturn() public override view returns (uint256) {
        uint256 estimateAssets = estimatedTotalAssets();

        uint256 debt = vault.strategies(address(this)).totalDebt;
        if (debt > estimateAssets) {
            return 0;
        } else {
            return estimateAssets - debt;
        }
    }

    /*
     * Our balance in CrETH plus balance of want
     */
    function estimatedTotalAssets() public override view returns (uint256) {

        uint256 underlying = underlyingBalanceStored();

        return want.balanceOf(address(this)).add(underlying);
    }

    /*
     * Provide a signal to the keeper that `tend()` should be called.
     * (keepers are always reimbursed by yEarn)
     *
     * NOTE: this call and `harvestTrigger` should never return `true` at the same time.
     * If we are in liquidation cushion we move
     */
    function tendTrigger(uint256 gasCost) public override view returns (bool) {
        gasCost; // silence UI warning
        if (harvestTrigger(gasCost)) {
            //harvest takes priority
            return false;
        }
        
        //we want to tend if there is a liquidity crisis
        uint256 cashAvailable = crETH.getCash();        
        if (cashAvailable <= liquidityCushion && cashAvailable > dustThreshold && underlyingBalanceStored() > dustThreshold) {
            return true;
        }

        return false;
    }

    function underlyingBalanceStored() public view returns (uint256 balance){
        uint256 currentCrETH = crETH.balanceOf(address(this));
        if(currentCrETH == 0){
            balance = 0;
        }else{
            balance = currentCrETH.mul(crETH.exchangeRateStored()).div(1e18);
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
         StrategyParams memory params = vault.strategies(address(this));

        // Should not trigger if strategy is not activated
        if (params.activation == 0) return false;

        // Should trigger if hadn't been called in a while
        if (block.number.sub(params.lastSync) >= maxReportDelay) return true;

        // If some amount is owed, pay it back
        // NOTE: Since debt is adjusted in step-wise fashion, it is appropiate to always trigger here,
        //       because the resulting change should be large (might not always be the case)
        uint256 outstanding = vault.debtOutstanding();
        if (outstanding > dustThreshold && crETH.getCash().add(want.balanceOf(address(this))) > 0) return true;

         // Check for profits and losses
        uint256 total = estimatedTotalAssets();
        if (total.add(dustThreshold) < params.totalDebt) return true; // We have a loss to report!

        uint256 profit = 0;
        if (total > params.totalDebt) profit = total.sub(params.totalDebt); // We've earned a profit!

        // Otherwise, only trigger if it "makes sense" economically (gas cost is <N% of value moved)
        uint256 credit = vault.creditAvailable();
        return (profitFactor * gasCost < credit.add(profit));
    }

    /***********
     * internal core logic
     *********** */
    /*
     * A core method.
     */
    function prepareReturn() internal override {

        if (crETH.balanceOf(address(this)) == 0) {
            //no position to harvest
            reserve = weth.balanceOf(address(this));
            return;
        }
        if (reserve != 0) {
            //reset reserve so it doesnt interfere anywhere else
            reserve = 0;
        }

        uint256 balanceInCr = crETH.balanceOfUnderlying(address(this));
        uint256 balanceInWeth = weth.balanceOf(address(this));
        uint256 total = balanceInCr.add(balanceInWeth);

        uint256 debt = vault.strategies(address(this)).totalDebt;

        if(total > debt){
            uint profit = total-debt;
            uint amountToFree = profit.add(outstanding);

            //we need to add outstanding to our profit
            if(balanceInWeth >= amountToFree){
                reserve = weth.balanceOf(address(this)) - amountToFree;
            }else{
                //change profit to what we can withdraw
                _withdrawSome(amountToFree.sub(balanceInWeth));
                balanceInWeth = weth.balanceOf(address(this));

                if(balanceInWeth > amountToFree){
                    reserve = balanceInWeth - amountToFree;
                }else{
                    reserve = 0;
                }

                
            }
            
        }else{
            uint256 bal = weth.balanceOf(address(this));
            if(bal <= outstanding){
                    reserve = 0;
            }else{
                reserve = bal - outstanding;
            }
        }

        
    }

    /*
     * Second core function. Happens after report call.
     *
     */

    function adjustPosition() internal override {
        //emergency exit is dealt with in prepareReturn
        if (emergencyExit) {
            return;
        }

        //we did state changing call in prepare return so this will be accurate
        uint liquidity = crETH.getCash();

        if(liquidity == 0){
            return;
        }

        uint wethBalance = weth.balanceOf(address(this));

        uint256 toKeep = 0;

        //to keep is the amount we need to hold to make the liqudity cushion full
        if(liquidity < liquidityCushion){
            toKeep = liquidityCushion.sub(liquidity);
        }

        //if we have more than enough weth then invest the extra
        if(wethBalance > toKeep){

            uint toInvest = wethBalance.sub(toKeep);

            //turn weth into eth first
            weth.withdraw(toInvest);
            //mint
            crETH.mint{value: toInvest}();

        }else if(wethBalance < toKeep){
            //free up the difference if we can
            uint toWithdraw = toKeep.sub(wethBalance);

            _withdrawSome(toWithdraw);
        }

    }

    /*************
     * Withdraw Up to the amount asked for
     * returns amount we really withdrew
     ******************** */
    function _withdrawSome(uint256 _amount) internal returns(uint256 amountWithdrawn) {
        
        //state changing
        uint balance = crETH.balanceOfUnderlying(address(this));
        if(_amount > balance){
            //cant withdraw more than we own
            _amount = balance;
        }

        //not state changing but OK because of previous call
        uint liquidity = crETH.getCash();
        amountWithdrawn = 0;
        if(liquidity == 0){
            return amountWithdrawn;
        }

        if(_amount <= liquidity){
                amountWithdrawn = _amount;
                //we can take all
                crETH.redeemUnderlying(amountWithdrawn);
            }else{
                //take all we can
                amountWithdrawn = liquidity-1;
                crETH.redeemUnderlying(amountWithdrawn); //safe as we return if liquidity == 0
        }

        //remember to turn eth to weth
        weth.deposit{value: address(this).balance}();
    }


    /*
     * Liquidate as many assets as possible to `want`, irregardless of slippage,
     * up to `_amount`. Any excess should be re-invested here as well.
     */
    function liquidatePosition(uint256 _amount) internal override {
        uint256 _balance = want.balanceOf(address(this));

        if(_balance >= _amount){
            //if we don't set reserve here withdrawer will be sent our full balance
            reserve = _balance.sub(_amount);
            return;
        }else{
            _withdrawSome(_amount - _balance);
        }
    }


    /*
     * Make as much capital as possible "free" for the Vault to take. Some slippage
     * is allowed.
     */
    function exitPosition() internal override {
        
        uint balance = crETH.balanceOfUnderlying(address(this));
        if(balance > 0){
            _withdrawSome(balance);
        }
        reserve = 0;

    }

    //lets leave
    function prepareMigration(address _newStrategy) internal override {
        crETH.transfer(_newStrategy, crETH.balanceOf(address(this)));
        want.safeTransfer(_newStrategy, want.balanceOf(address(this)));
    }



    function protectedTokens() internal override view returns (address[] memory) {
        address[] memory protected = new address[](2);
        protected[0] = address(want);
        protected[1] = address(crETH);
        return protected;
    }

   
}
