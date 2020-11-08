pragma solidity ^0.6.12;
import {BaseStrategyV0_1_3, StrategyParams} from "./BaseStrategyV0_1_3.sol";
pragma experimental ABIEncoderV2;

import "./GenericLender/IGenericLender.sol";

import "@openzeppelinV3/contracts/token/ERC20/IERC20.sol";
import "@openzeppelinV3/contracts/math/SafeMath.sol";
import "@openzeppelinV3/contracts/utils/Address.sol";
import "@openzeppelinV3/contracts/token/ERC20/SafeERC20.sol";

/********************
 *   A lender optimisation strategy for any erc20 asset
 *   Made by SamPriestley.com
 *   https://github.com/Grandthrax/yearnv2/blob/master/contracts/LenderYieldOptimiser.sol
 *
 ********************* */


contract LenderYieldOptimiser is BaseStrategyV0_1_3{

    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    IGenericLender[] public lenders;


    constructor(address _vault) public BaseStrategyV0_1_3(_vault) {
        // You can set these parameters on deployment to whatever you want
        minReportDelay = 6300;
        profitFactor = 100;
        debtThreshold = 1 gwei;
    }


    // ******** OVERRIDE THESE METHODS FROM BASE CONTRACT ************

    function name() external override pure returns (string memory) {
        // Add your own name here, suggestion e.g. "StrategyCreamYFI"
        return "StrategyLenderYieldOptimiser";
    }

    function addLender(address a) public{

    }
    function removeLender(address a) public{

    }

    // lent assets plus loose assets
    function estimatedTotalAssets() public override view returns (uint256) {
        
        uint256 nav = lentTotalAssets();
        nav += want.balanceOf(address(this));

        return nav;
    }

    //cycle all lenders and collect balances
    function lentTotalAssets() public view returns (uint256) {
        uint nav = 0;
        for(uint i = 0; i < lenders.length; i++){
            nav += lenders[i].nav();
        }
        return nav;
     }

    //we need to free up profit plus _debtOutstanding. 
    //If _debtOutstanding is more than we can free we get as much as possible
    function prepareReturn(uint256 _debtOutstanding) internal override returns (uint256 _profit) {
        uint256 lentAssets = lentTotalAssets();

        uint256 looseAssets = want.balanceOf(address(this));

        uint256 total = looseAssets.add(lentAssets);


        if (lentAssets == 0) {
            //no position to harvest or profit to report
            if(_debtOutstanding > looseAssets){
                setReserve(0);
            }else{
                setReserve(looseAssets.sub(_debtOutstanding));
            }
            
            return 0;
        }
        if (getReserve() != 0) {
            //reset reserve so it doesnt interfere anywhere else
            setReserve(0);
        }

        uint256 debt = vault.strategies(address(this)).totalDebt;

        if(total > debt){
            uint profit = total-debt;
            uint amountToFree = profit.add(_debtOutstanding);

            //we need to add outstanding to our profit
            if(looseAssets >= amountToFree){
                setReserve(looseAssets - amountToFree);
            }else{
                //change profit to what we can withdraw
                _withdrawSome(amountToFree.sub(looseAssets));
                uint256 newLoose = want.balanceOf(address(this));

                if(newLoose > amountToFree){
                    setReserve(newLoose - amountToFree);
                }else{
                    setReserve(0);
                }

            }

            return profit;

        } else {
        
            if(looseAssets <= _debtOutstanding){
                     setReserve(0);
            }else{
                setReserve(looseAssets - _debtOutstanding);
            }

            return 0;
        }
    }

    struct lendStatus{
        uint256 assets;
        uint256 rate;
    }

    /*
    * Key logic.
    *   The algorithm moves assets from lowest return to highest
    *   like a very slow idiots bubble sort
    *   we ignore debt outstanding for an easy life
    *
    */
    function adjustPosition(uint256 _debtOutstanding) internal override {
        //emergency exit is dealt with at beginning of harvest
        if (emergencyExit) {
            return;
        }
        //reset reserve and refund some gas
        setReserve(0);

        //all loose assets are to be invested
        uint256 looseAssets = want.balanceOf(address(this));

        lendStatus[] memory lendStatuses;
        
        /*//if we have more than enough weth then invest the extra
        if(wethBalance > toKeep){

            uint toInvest = wethBalance.sub(toKeep);

            //turn weth into eth first
            IWETH(weth).withdraw(toInvest);
            //mint
            Bank(bank).deposit{value: toInvest}();

        }else if(wethBalance < toKeep){
            //free up the difference if we can
            uint toWithdraw = toKeep.sub(wethBalance);

            _withdrawSome(toWithdraw);
        }*/
    }

    //cycle through withdrawing from worst rate first
    function _withdrawSome(uint256 _amount) internal returns(uint256 amountWithdrawn) {
        /*
        //state changing
        uint balance = bankBalance();
        if(_amount > balance) {
            //cant withdraw more than we own
            _amount = balance;
        }

        //not state changing but OK because of previous call
        uint liquidity = bank.balance;
        amountWithdrawn = 0;
        if(liquidity == 0) {
            return amountWithdrawn;
        }

        if(_amount <= liquidity) {
            amountWithdrawn = _amount;
            //we can take all
            withdrawUnderlying(amountWithdrawn);
        } else {
            //take all we can
            withdrawUnderlying(amountWithdrawn);
        }

        //in case we get back less than expected
        amountWithdrawn = address(this).balance;

        //remember to turn eth to weth
        IWETH(weth).deposit{value: amountWithdrawn}();*/
    }

    /*
     * Make as much capital as possible "free" for the Vault to take. Some slippage
     * is allowed, since when this method is called the strategist is no longer receiving
     * their performance fee. The goal is for the strategy to divest as quickly as possible
     * while not suffering exorbitant losses. This function is used during emergency exit
     * instead of `prepareReturn()`
     */
    function exitPosition() internal override {
        uint balance = lentTotalAssets();
        if(balance > 0){
            _withdrawSome(balance);
        }
        setReserve(0);
    }

    /*
     * Liquidate as many assets as possible to `want`, irregardless of slippage,
     * up to `_amountNeeded`. Any excess should be re-invested here as well.
     */
    function liquidatePosition(uint256 _amountNeeded) internal override returns (uint256 _amountFreed) {
         uint256 _balance = want.balanceOf(address(this));

        if(_balance >= _amountNeeded){
            //if we don't set reserve here withdrawer will be sent our full balance
            setReserve(_balance.sub(_amountNeeded));
            return _amountNeeded;
        }else{
            uint received = _withdrawSome(_amountNeeded - _balance).add(_balance);
            if(received > _amountNeeded){
                return  _amountNeeded;
            }else{
                return received;
            }

        }
    }

    // NOTE: Can override `tendTrigger` and `harvestTrigger` if necessary

    /*
     * Do anything necesseary to prepare this strategy for migration, such
     * as transfering any reserve or LP tokens, CDPs, or other tokens or stores of value.
     */
    function prepareMigration(address _newStrategy) internal override {
        exitPosition();
        want.safeTransfer(_newStrategy, want.balanceOf(address(this)));
    }

    // Override this to add all tokens/tokenized positions this contract manages
    // on a *persistant* basis (e.g. not just for swapping back to want ephemerally)
    // NOTE: Do *not* include `want`, already included in `sweep` below
    //
    // Example:
    //
    //    function protectedTokens() internal override view returns (address[] memory) {
    //      address[] memory protected = new address[](3);
    //      protected[0] = tokenA;
    //      protected[1] = tokenB;
    //      protected[2] = tokenC;
    //      return protected;
    //    }
    function protectedTokens() internal override view returns (address[] memory) {
        address[] memory protected = new address[](2);
        protected[0] = address(want);
        return protected;
    }

}