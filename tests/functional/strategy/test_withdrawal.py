import brownie


def test_withdraw(gov, token, vault, strategy, rando):

    assert strategy.estimatedTotalAssets() == 0
    token.approve(vault, token.balanceOf(gov), {"from": gov})
    vault.deposit(token.balanceOf(gov) // 2, {"from": gov})
    strategy.harvest({"from": gov})  # Seed some debt in there
    assert strategy.estimatedTotalAssets() > 0

    balance = strategy.estimatedTotalAssets()
    print(balance)

    vault.withdraw(vault.balanceOf(gov), {"from": gov})
    assert strategy.estimatedTotalAssets() == 0


#  strategy.withdraw(balance // 2, {"from": vault.address})
#  assert strategy.estimatedTotalAssets() == balance // 2


# Not just anyone can call it
#  with brownie.reverts():
#     strategy.withdraw(balance // 2, {"from": rando})

# Anything over what we can liquidate is totally withdrawn
# strategy.withdraw(balance, {"from": vault.address})
# assert strategy.estimatedTotalAssets() == 0
