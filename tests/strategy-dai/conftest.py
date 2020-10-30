import pytest
from brownie import Wei

@pytest.fixture
def dai(interface):
    yield interface.ERC20('0x6b175474e89094c44da98b954eedeac495271d0f')

#any strategy just deploys base strategy can be used because they have the same interface
@pytest.fixture(scope='session')
def strategy_generic(YearnDaiCompStratV2):
    #print('Do you want to use deployed strategy? (y)')
    #if input() == 'y' or 'Y':
    print('Enter strategy address')
    yield YearnDaiCompStratV2.at(input())

@pytest.fixture(scope='session')
def vault_generic(Vault):
    print('Enter vault address')
    yield Vault.at(input())

@pytest.fixture(scope='session')
def strategist_generic(accounts):
    print('Enter strategist address')
    yield accounts.at(input(), force=True)

@pytest.fixture(scope='session')
def governance_generic(accounts):
    print('Enter governance address')
    yield accounts.at(input(), force=True)

@pytest.fixture(scope='session')
def whale_generic(accounts):
    print('Enter whale address')
    yield accounts.at(input(), force=True)

@pytest.fixture(scope='session')
def want_generic(interface):
    print('Enter want address')
    yieldinterface.ERC20(input())

@pytest.fixture(scope='session')
def live_vault(Vault):
    yield Vault.at('0x9B142C2CDAb89941E9dcd0B6C1cf6dEa378A8D7C')

@pytest.fixture(scope='session')
def live_strategy(YearnDaiCompStratV2):
    yield YearnDaiCompStratV2.at('0x4C6e9d7E5d69429100Fcc8afB25Ea980065e2773')

@pytest.fixture(scope='session')
def dai(interface):
    yield interface.ERC20('0x6b175474e89094c44da98b954eedeac495271d0f')

#uniwethwbtc
@pytest.fixture(scope='session')
def uni_wethwbtc(interface):
    yield interface.ERC20('0xBb2b8038a1640196FbE3e38816F3e67Cba72D940')


@pytest.fixture(scope='session')
def samdev(accounts):
    yield accounts.at('0xC3D6880fD95E06C816cB030fAc45b3ffe3651Cb0', force=True)

@pytest.fixture(scope='session')
def comp(interface):
    yield interface.ERC20('0xc00e94Cb662C3520282E6f5717214004A7f26888')

@pytest.fixture(scope='session')
def cdai(interface):
    yield interface.CErc20I('0x5d3a536e4d6dbd6114cc1ead35777bab948e3643')

#@pytest.fixture(autouse=True)
#def isolation(fn_isolation):
#    pass
@pytest.fixture(scope="module", autouse=True)
def shared_setup(module_isolation):
    pass

@pytest.fixture
def gov(accounts):
    yield accounts[0]

@pytest.fixture
def whale(accounts, history, web3):
    acc = accounts.at('0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8', force=True)
    yield acc

#uniswap weth/wbtc
@pytest.fixture()
def whaleU(accounts, history, web3, shared_setup):
    acc = accounts.at('0xf2d373481e1da4a8ca4734b28f5a642d55fda7d3', force=True)
    yield acc
    

@pytest.fixture()
def strategist(accounts, whale, dai):
    dai.transfer(accounts[1], Wei('10000 ether'), {'from': whale})
    dai.transfer(accounts[0], Wei('10000 ether'), {'from': whale})
    yield accounts[1]

@pytest.fixture
def rando(accounts):
    yield accounts[9]



@pytest.fixture()
def vault(gov, dai, Vault):
    # Deploy the Vault
    vault = gov.deploy(
        Vault, dai, gov, gov, "Yearn DAI v2", "y2DAI"
    )
    yield vault

@pytest.fixture()
def seededvault(vault, dai, rando):
   # Make it so vault has some AUM to start
    amount = Wei('10000 ether')
    token.approve(vault, amount, {"from": rando})
    vault.deposit(amount, {"from": rando})
    assert token.balanceOf(vault) == amount
    assert vault.totalDebt() == 0  # No connected strategies yet
    yield vault

@pytest.fixture()
def strategy(gov, strategist, dai, vault, YearnDaiCompStratV2):
    strategy = strategist.deploy(YearnDaiCompStratV2, vault)

    vault.addStrategy(
        strategy,
        dai.totalSupply(),  # Debt limit of 20% of token supply 
        dai.totalSupply(),  # Rate limt of 0.1% of token supply per block
        50,  # 0.5% performance fee for Strategist
        {"from": gov},
    )
    yield strategy

@pytest.fixture()
def largerunningstrategy(gov, strategy, dai, vault, whale):

    amount = Wei('499000 ether')
    dai.approve(vault, amount, {'from': whale})
    vault.deposit(amount, {'from': whale})    

    strategy.harvest({'from': gov})
    
    #do it again with a smaller amount to replicate being this full for a while
    amount = Wei('1000 ether')
    dai.approve(vault, amount, {'from': whale})
    vault.deposit(amount, {'from': whale})   
    strategy.harvest({'from': gov})
    
    yield strategy

@pytest.fixture()
def enormousrunningstrategy(gov, largerunningstrategy, dai, vault, whale):
    dai.approve(vault, dai.balanceOf(whale), {'from': whale})
    vault.deposit(dai.balanceOf(whale), {'from': whale})   
   
    collat = 0

    while collat < largerunningstrategy.collateralTarget() / 1.001e18:

        largerunningstrategy.harvest({'from': gov})
        deposits, borrows = largerunningstrategy.getCurrentPosition()
        collat = borrows / deposits
        
    
    yield largerunningstrategy

