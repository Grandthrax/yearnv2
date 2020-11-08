pragma solidity ^0.6.12;
import "./BaseStrategyV0_1_3.sol";
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

        //we do this horrible thing because you can't compare strings in solidity
        require(keccak256(bytes(apiVersion())) == keccak256(bytes(VaultAPI(_vault).apiVersion())), "WRONG VERSION");
    }


    // ******** OVERRIDE THESE METHODS FROM BASE CONTRACT ************

    function name() external override pure returns (string memory) {
        // Add your own name here, suggestion e.g. "StrategyCreamYFI"
        return "StrategyLenderYieldOptimiser";
    }

    //management functions
    function addLender(address a) public management{
       IGenericLender n = IGenericLender(a);

        for(uint i = 0; i < lenders.length; i++){
            require(a != address(lenders[i]), "Already Added");
        }
        lenders.push(n);
    }
    function removeLender(address a) public management{
       for(uint i = 0; i < lenders.length; i++){
            
            if(a == address(lenders[i]))
            {
                //withdraw first
                require(lenders[i].withdrawAll(), "WITHDRAW FAILED");
                //if balance to spend
                if(want.balanceOf(address(this)) > 0){
                    adjustPosition(0);
                }

                //put the last index here
                //remove last index
                if(i != lenders.length){
                    lenders[i] = lenders[lenders.length-1];
                }
                delete lenders[lenders.length-1];
                return;
            }
        }
        require(false, "NOT LENDER");
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

    /*
    * Key logic.
    *   The algorithm moves assets from lowest return to highest
    *   like a very slow idiots bubble sort
    *   we ignore debt outstanding for an easy life
    *
    */
    function adjustPosition(uint256 _debtOutstanding) internal override {

        _debtOutstanding; //ignored
        //emergency exit is dealt with at beginning of harvest
        if (emergencyExit) {
            return;
        }
        //reset reserve and refund some gas
        setReserve(0);

        //all loose assets are to be invested
        uint256 looseAssets = want.balanceOf(address(this));

        // our simple algo
        // get the lowest apr strat and nav
        // cycle through and see who could take its funds plus want for the highest apr
        uint256 lowestApr = uint256(-1);
        uint256 lowest = 0;
        uint256 lowestNav = 0;
        for(uint i = 0; i < lenders.length; i++){
            if(lenders[i].hasAssets()){
                uint256 apr = lenders[i].apr();
                if(apr < lowestApr){
                    lowestApr = apr;
                    lowest = i;
                    lowestNav = lenders[i].nav();
                }
             }
        }

        uint256 toAdd = lowestNav.add(looseAssets);

        uint256 highestApr = 0;
        uint256 highest = 0;

        for(uint i = 0; i < lenders.length; i++){
           
            uint256 apr = lenders[i].aprAfterDeposit(toAdd);
            if(apr > highestApr){
                highestApr = apr;
                highest = i;
            }
             
        }


        //if we can improve apr by withdrawing we do so
        if(highestApr > lowestApr){
            lenders[lowest].withdrawAll();
        }

        want.transfer(address(lenders[highest]), want.balanceOf(address(this)));
        lenders[highest].deposit();

    }


    //cycle through withdrawing from worst rate first
    function _withdrawSome(uint256 _amount) internal returns(uint256 amountWithdrawn) {
     
        //most situations this will only run once. Only big withdrawals will be a gas guzzler
        while(amountWithdrawn < _amount){
            uint256 lowestApr = uint256(-1);
            uint256 lowest = 0;
            for(uint i = 0; i < lenders.length; i++){
                if(lenders[i].hasAssets()){
                    uint256 apr = lenders[i].apr();
                    if(apr < lowestApr){
                        lowestApr = apr;
                        lowest = i;
                    }
                }
                
            }
            if(!lenders[lowest].hasAssets()){
                return amountWithdrawn;
            }
            amountWithdrawn += lenders[lowest].withdraw(_amount);
        }
    }


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

    modifier management(){
        require(msg.sender == governance() || msg.sender == strategist, "!management");
        _;
    }

}