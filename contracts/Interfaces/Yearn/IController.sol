pragma solidity ^0.6.9;

interface IController {
    function withdraw(address, uint256) external;

    function balanceOf(address) external view returns (uint256);

    function earn(address, uint256) external;

    function want(address) external view returns (address);

    function rewards() external view returns (address);

    function vaults(address) external view returns (address);

    function approveStrategy(address, address) external;

    function setStrategy(address, address) external;

    function strategies(address) external view returns (address);
}
