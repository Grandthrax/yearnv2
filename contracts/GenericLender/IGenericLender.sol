pragma solidity 0.6.12;

interface IGenericLender {
    function nav() external view returns (uint256);
    function apr() external view returns (uint256);
    function withdraw(uint256 amount) external returns (uint256);
    function deposit() external;
    function withdrawAll() external returns (bool);
    function enabled() external returns (bool);
    function hasAssets() external returns (bool);
    function minApr(uint256 amount) external view returns (uint256);
    function aprAfterDeposit(uint256 amount) external view returns (uint256);
}
