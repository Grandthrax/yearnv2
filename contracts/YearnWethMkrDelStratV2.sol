pragma solidity ^0.6.12;
pragma experimental ABIEncoderV2;

import "@openzeppelinV3/contracts/token/ERC20/IERC20.sol";
import "@openzeppelinV3/contracts/math/SafeMath.sol";
import "@openzeppelinV3/contracts/utils/Address.sol";
import "@openzeppelinV3/contracts/token/ERC20/SafeERC20.sol";

import "./Interfaces/Maker/Maker.sol";
import "./Interfaces/UniswapInterfaces/IUniswapV2Router02.sol";

import "./BaseStrategyV0_1_1.sol";


//extend the vault API from base strategy
interface IVaultE is VaultAPI{
     function deposit(uint256 _amount) external returns (uint256);
     function balanceOf(address _address) external view returns (uint256);
     function withdraw(uint256 _amount) external returns (uint256);
     function pricePerShare() external view returns (uint256);
}

contract StrategyMKRVaultDAIDelegate is BaseStrategyV0_1_1{
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    //token is weth?
    address public constant token = address(0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2);
    address public constant weth = address(0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2);
    address public constant dai = address(0x6B175474E89094C44Da98b954EedeAC495271d0F);

    address public cdp_manager = address(0x5ef30b9986345249bc32d8928B7ee64DE9435E39);
    address public vat = address(0x35D1b3F3D7966A1DFe207aa4514C12a259A0492B);
    address public mcd_join_eth_a = address(0x2F0b23f53734252Bda2277357e97e1517d6B042A);
    address public mcd_join_dai = address(0x9759A6Ac90977b93B58547b4A71c78317f391A28);
    address public mcd_spot = address(0x65C79fcB50Ca1594B025960e539eD7A9a6D434A3);
    address public jug = address(0x19c0976f590D67707E62397C87829d896Dc0f1F1);

    address public eth_price_oracle = address(0xCF63089A8aD2a9D8BD6Bb8022f3190EB7e1eD0f1);
    address public constant yVaultDAI = address(0x9B142C2CDAb89941E9dcd0B6C1cf6dEa378A8D7C);

    address public constant unirouter = address(0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D);

    uint256 public c = 20000;
    uint256 public c_safe = 30000;
    uint256 public constant c_base = 10000;


    bytes32 public constant ilk = "ETH-A";

    uint256 public maxReportDelay = 50; //6300 is once a day. lower vaule used for testing

    uint256 public profitFactor = 50; // multiple before triggering harvest
    uint256 public dustThreshold = 0.01 ether; // multiple before triggering harvest



    uint256 public cdpId;

    constructor(address _vault) public BaseStrategyV0_1_1(_vault){
        cdpId = ManagerLike(cdp_manager).open(ilk, address(this));
        _approveAll();
    }


    function setBorrowCollateralizationRatio(uint256 _c) external {
        require(msg.sender == governance() || msg.sender == strategist, "!management");
        c = _c;
    }

    function setWithdrawCollateralizationRatio(uint256 _c_safe) external {
        require(msg.sender == governance() || msg.sender == strategist, "!management");
        c_safe = _c_safe;
    }

    function setOracle(address _oracle) external {
        require(msg.sender == governance() || msg.sender == strategist, "!management");
        eth_price_oracle = _oracle;
    }

    // optional
    function setMCDValue(
        address _manager,
        address _ethAdapter,
        address _daiAdapter,
        address _spot,
        address _jug
    ) external {
        require(msg.sender == governance() || msg.sender == strategist, "!management");
        cdp_manager = _manager;
        vat = ManagerLike(_manager).vat();
        mcd_join_eth_a = _ethAdapter;
        mcd_join_dai = _daiAdapter;
        mcd_spot = _spot;
        jug = _jug;
    }

    function protectedTokens() internal override view returns (address[] memory) {
        address[] memory protected = new address[](3);
        protected[0] = address(want);
        protected[1] = yVaultDAI;
        protected[2] = dai;
        return protected;
    }

    function _approveAll() internal {
        IERC20(token).approve(mcd_join_eth_a, uint256(-1));
        IERC20(dai).approve(mcd_join_dai, uint256(-1));
        IERC20(dai).approve(yVaultDAI, uint256(-1));
        IERC20(dai).approve(unirouter, uint256(-1));
    }

    function deposit() internal {
        uint256 _token = IERC20(token).balanceOf(address(this));
        if(_token > outstanding){
            _token = _token - outstanding;
        }else{
            return;
        }

        if (_token > 0) {
            uint256 p = _getPrice();
            uint256 _draw = _token.mul(p).mul(c_base).div(c).div(1e18);
            // approve adapter to use token amount
            require(_checkDebtCeiling(_draw), "debt ceiling is reached!");
            _lockWETHAndDrawDAI(_token, _draw);
        }
        // approve yVaultDAI use DAI
        IVaultE(yVaultDAI).deposit(_token);
    }

    function _getPrice() internal view returns (uint256 p) {
        (uint256 _read, ) = OSMedianizer(eth_price_oracle).read();
        (uint256 _foresight, ) = OSMedianizer(eth_price_oracle).foresight();
        p = _foresight < _read ? _foresight : _read;
    }

    function _checkDebtCeiling(uint256 _amt) internal view returns (bool) {
        (, , , uint256 _line, ) = VatLike(vat).ilks(ilk);
        uint256 _debt = getTotalDebtAmount().add(_amt);
        if (_line.div(1e27) < _debt) {
            return false;
        }
        return true;
    }

    function _lockWETHAndDrawDAI(uint256 wad, uint256 wadD) internal {
        address urn = ManagerLike(cdp_manager).urns(cdpId);

        // GemJoinLike(mcd_join_eth_a).gem().approve(mcd_join_eth_a, wad);
        GemJoinLike(mcd_join_eth_a).join(urn, wad);
        ManagerLike(cdp_manager).frob(cdpId, toInt(wad), _getDrawDart(urn, wadD));
        ManagerLike(cdp_manager).move(cdpId, address(this), wadD.mul(1e27));
        if (VatLike(vat).can(address(this), address(mcd_join_dai)) == 0) {
            VatLike(vat).hope(mcd_join_dai);
        }
        DaiJoinLike(mcd_join_dai).exit(address(this), wadD);
    }

    function _getDrawDart(address urn, uint256 wad) internal returns (int256 dart) {
        uint256 rate = JugLike(jug).drip(ilk);
        uint256 _dai = VatLike(vat).dai(urn);

        // If there was already enough DAI in the vat balance, just exits it without adding more debt
        if (_dai < wad.mul(1e27)) {
            dart = toInt(wad.mul(1e27).sub(_dai).div(rate));
            dart = uint256(dart).mul(rate) < wad.mul(1e27) ? dart + 1 : dart;
        }
    }

    function toInt(uint256 x) internal pure returns (int256 y) {
        y = int256(x);
        require(y >= 0, "int-overflow");
    }

    function expectedReturn() public override view returns (uint256){
        return vault.expectedReturn();
    }


    // Withdraw partial funds, normally used with a vault withdrawal
    function liquidatePosition(uint256 _amount) internal override {
     
        uint256 _balance = IERC20(want).balanceOf(address(this));
        if(_balance >= _amount){
            //if we don't set reserve here withdrawer will be sent our full balance
            reserve = _balance.sub(_amount);
            return;
        }
        if (_balance < _amount) {
            _amount = _withdrawSome(_amount.sub(_balance));
            _amount = _amount.add(_balance);
        }
    }

    function _withdrawSome(uint256 _amount) internal returns (uint256) {
        if (getTotalDebtAmount() != 0 && getmVaultRatio(_amount) < c_safe.mul(1e2)) {
            uint256 p = _getPrice();
            _wipe(_withdrawDaiLeast(_amount.mul(p).div(1e18)));
        }

        _freeWETH(_amount);

        return _amount;
    }

    function _freeWETH(uint256 wad) internal {
        ManagerLike(cdp_manager).frob(cdpId, -toInt(wad), 0);
        ManagerLike(cdp_manager).flux(cdpId, address(this), wad);
        GemJoinLike(mcd_join_eth_a).exit(address(this), wad);
    }

    function _wipe(uint256 wad) internal {
        // wad in DAI
        address urn = ManagerLike(cdp_manager).urns(cdpId);

        DaiJoinLike(mcd_join_dai).join(urn, wad);
        ManagerLike(cdp_manager).frob(cdpId, 0, _getWipeDart(VatLike(vat).dai(urn), urn));
    }

    function _getWipeDart(uint256 _dai, address urn) internal view returns (int256 dart) {
        (, uint256 rate, , , ) = VatLike(vat).ilks(ilk);
        (, uint256 art) = VatLike(vat).urns(ilk, urn);

        dart = toInt(_dai / rate);
        dart = uint256(dart) <= art ? -dart : -toInt(art);
    }

    // Withdraw all funds, normally used when migrating strategies
    function prepareMigration(address _newStrategy) internal override {
        _withdrawAll();

        _swap(IERC20(dai).balanceOf(address(this)));
        uint256 balance = IERC20(want).balanceOf(address(this));

        IERC20(want).safeTransfer(_newStrategy, balance);
    }

    function _withdrawAll() internal {
        IVaultE vault = IVaultE(yVaultDAI);
        vault.withdraw(vault.balanceOf(address(this))); // get Dai
        _wipe(getTotalDebtAmount().add(1)); // in case of edge case
        _freeWETH(balanceOfmVault());
    }

    function estimatedTotalAssets() public override view returns (uint256) {
        return balanceOfWant().add(balanceOfmVault());
    }

    function balanceOfWant() public view returns (uint256) {
        return IERC20(want).balanceOf(address(this));
    }

    function balanceOfmVault() public view returns (uint256) {
        uint256 ink;
        address urnHandler = ManagerLike(cdp_manager).urns(cdpId);
        (ink, ) = VatLike(vat).urns(ilk, urnHandler);
        return ink;
    }

    function prepareReturn() internal override {
        
        uint256 v = getUnderlyingDai();
        uint256 d = getTotalDebtAmount();

        uint256 _before = IERC20(want).balanceOf(address(this));
        uint256 profit = 0;
        if(v > d){
            profit = v.sub(d);
            _swap(_withdrawDaiMost(profit));

        }

        reserve = _before;

        if(outstanding < _before){
            reserve = _before - outstanding;
        }else{
            reserve = 0;
        }

        
        
    }

    function adjustPosition() internal override {

        //if we over 
        repay();
        //todo move to adjust position
         deposit();
    }

     function exitPosition() internal override{

         //todo
     }

    function tendTrigger(uint256 gasCost) public override view returns (bool) {
        
        return false;
    }

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
        if (outstanding > dustThreshold) return true;

         // Check for profits and losses
        uint256 total = estimatedTotalAssets();
        if (total.add(dustThreshold) < params.totalDebt) return true; // We have a loss to report!

        uint256 profit = 0;
        if (total > params.totalDebt) profit = total.sub(params.totalDebt); // We've earned a profit!

        // Otherwise, only trigger if it "makes sense" economically (gas cost is <N% of value moved)
        uint256 credit = vault.creditAvailable();
        return (profitFactor * gasCost < credit.add(profit));
    }
       

    function shouldDraw() external view returns (bool) {
        uint256 _safe = c.mul(1e2);
        uint256 _current = getmVaultRatio(0);
        if (_current > c_base.mul(c_safe).mul(1e2)) {
            _current = c_base.mul(c_safe).mul(1e2);
        }
        return (_current > _safe);
    }

    function drawAmount() public view returns (uint256) {
        uint256 _safe = c.mul(1e2);
        uint256 _current = getmVaultRatio(0);
        if (_current > c_base.mul(c_safe).mul(1e2)) {
            _current = c_base.mul(c_safe).mul(1e2);
        }
        if (_current > _safe) {
            uint256 _eth = balanceOfmVault();
            uint256 _diff = _current.sub(_safe);
            uint256 _draw = _eth.mul(_diff).div(_safe).mul(c_base).mul(1e2).div(_current);
            return _draw.mul(_getPrice()).div(1e18);
        }
        return 0;
    }

    //open draw?
 /*   function draw() external {
        uint256 _drawD = drawAmount();
        if (_drawD > 0) {
            _lockWETHAndDrawDAI(0, _drawD);
            IVaultE(yVaultDAI).depositAll();
        }
    }*/

    function shouldRepay() external view returns (bool) {
        uint256 _safe = c.mul(1e2);
        uint256 _current = getmVaultRatio(0);
        _current = _current.mul(105).div(100); // 5% buffer to avoid deposit/rebalance loops
        return (_current < _safe);
    }

    function repayAmount() public view returns (uint256) {
        uint256 _safe = c.mul(1e2);
        uint256 _current = getmVaultRatio(0);
        if(_current == uint256(-1)){
            return 0;
        }
        _current = _current.mul(105).div(100); // 5% buffer to avoid deposit/rebalance loops
        if (_current < _safe) {
            uint256 d = getTotalDebtAmount();
            uint256 diff = _safe.sub(_current);
            return d.mul(diff).div(_safe);
        }
        return 0;
    }

    function repay() internal {
        uint256 free = repayAmount();
        if (free > 0) {
            _wipe(_withdrawDaiLeast(free));
        }
    }

    function forceRebalance(uint256 _amount) external {
        require(msg.sender == governance() || msg.sender == strategist, "!management");
        _wipe(_withdrawDaiLeast(_amount));
    }

    function getTotalDebtAmount() public view returns (uint256) {
        uint256 art;
        uint256 rate;
        address urnHandler = ManagerLike(cdp_manager).urns(cdpId);
        (, art) = VatLike(vat).urns(ilk, urnHandler);
        (, rate, , , ) = VatLike(vat).ilks(ilk);
        return art.mul(rate).div(1e27);
    }

    function getmVaultRatio(uint256 amount) public view returns (uint256) {
        uint256 spot; // ray
        uint256 liquidationRatio; // ray
        uint256 denominator = getTotalDebtAmount();

        if (denominator == 0) {
            return uint256(-1);
        }

        (, , spot, , ) = VatLike(vat).ilks(ilk);
        (, liquidationRatio) = SpotLike(mcd_spot).ilks(ilk);
        uint256 delayedCPrice = spot.mul(liquidationRatio).div(1e27); // ray

        uint256 _balance = balanceOfmVault();
        if (_balance < amount) {
            _balance = 0;
        } else {
            _balance = _balance.sub(amount);
        }

        uint256 numerator = _balance.mul(delayedCPrice).div(1e18); // ray
        return numerator.div(denominator).div(1e3);
    }

    //the values of our share of underlying dai
    function getUnderlyingDai() public view returns (uint256) {
        return IERC20(yVaultDAI).balanceOf(address(this)).mul(IVaultE(yVaultDAI).pricePerShare()).div(1e18);
    }

    //not sure difference
    function _withdrawDaiMost(uint256 _amount) internal returns (uint256) {
        uint256 _shares = _amount.mul(1e18).div(IVaultE(yVaultDAI).pricePerShare());

        if (_shares > IERC20(yVaultDAI).balanceOf(address(this))) {
            _shares = IERC20(yVaultDAI).balanceOf(address(this));
        }

        uint256 _before = IERC20(dai).balanceOf(address(this));
        IVaultE(yVaultDAI).withdraw(_shares);
        uint256 _after = IERC20(dai).balanceOf(address(this));
        return _after.sub(_before);
    }

    // withdraw as close to amount as possible. can go just above
    function _withdrawDaiLeast(uint256 _amount) internal returns (uint256) {
        uint256 _shares = _amount.mul(1e18).div(IVaultE(yVaultDAI).pricePerShare()) + 1;

        if (_shares > IERC20(yVaultDAI).balanceOf(address(this))) {
            _shares = IERC20(yVaultDAI).balanceOf(address(this));
        }

        uint256 _before = IERC20(dai).balanceOf(address(this));
        IVaultE(yVaultDAI).withdraw(_shares);
        uint256 _after = IERC20(dai).balanceOf(address(this));
        return _after.sub(_before);
    }

    function _swap(uint256 _amountIn) internal {
        address[] memory path = new address[](2);
        path[0] = address(dai);
        path[1] = address(want);

        // approve unirouter to use dai
        IUniswapV2Router02(unirouter).swapExactTokensForTokens(_amountIn, 0, path, address(this), now.add(1 days));
    }

 
}