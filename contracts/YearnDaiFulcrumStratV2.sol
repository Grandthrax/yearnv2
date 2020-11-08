pragma solidity ^0.6.12;
pragma experimental ABIEncoderV2;

import "@openzeppelinV3/contracts/token/ERC20/IERC20.sol";
import "@openzeppelinV3/contracts/math/SafeMath.sol";
import "@openzeppelinV3/contracts/token/ERC20/SafeERC20.sol";

import "./Interfaces/UniswapInterfaces/IWETH.sol";

import "./Interfaces/Yearn/IController.sol";

import "./BaseStrategyV0_1_1.sol";

interface LoanToken{

}

/********************
 *   A DAI Fulcrum strategy with a liquidity buffer to ensure we don't end up in crisis.
 *   Made by SamPriestley.com
 *   https://github.com/Grandthrax/yearnv2/blob/master/contracts/YearnWethCreamStratV2.sol
 *
 ********************* */

contract YearnDaiFulcrumStratV2  {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    string public constant name = "YearnWethCreamStratV2";

    //Only three tokens we use
    LoanToken public constant lToken = LoanToken(address(0x493C57C4763932315A328269E1ADaD09653B9081));

    uint256 public maxReportDelay = 50; //6300 is once a day. lower vaule used for testing

    //Operating variables
    uint256 public liquidityCushion = 10000 ether; // 3000 dai

    uint256 public profitFactor = 50; // multiple before triggering harvest
    uint256 public dustThreshold = 0.01 ether; // multiple before triggering harvest




   
}
