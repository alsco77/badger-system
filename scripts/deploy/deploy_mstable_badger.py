import time

from brownie import (
    accounts,
    network,
    MStableVoterProxy,
    SettV4,
    StrategyMStableVaultImbtc,
    StrategyMStableVaultFpMbtcHbtc,
    AdminUpgradeabilityProxy,
)

from scripts.systems.mstable_system import MStableSystem
from config.badger_config import sett_config
from helpers.registry import registry
from dotmap import DotMap
from rich.console import Console
from helpers.registry.artifacts import artifacts
from helpers.proxy_utils import deploy_proxy_admin

import click

console = Console()

sleep_between_tx = 1


def main():

    dev = connect_account()

    dualGovernance = accounts.at(
        "0xCa045cC466f14C33a516D98abcab5C55C2f5112c", force=True
    )
    governance = accounts.at(
        "0xB65cef03b9B89f99517643226d76e286ee999e77", force=True
    )  # devMultisig
    strategist = accounts.at(
        "0xDA25ee226E534d868f0Dd8a459536b03fEE9079b", force=True
    )  # deployer
    keeper = accounts.at("0x872213E29C85d7e30F1C8202FC47eD1Ec124BB1D", force=True)
    guardian = accounts.at("0x29F7F8896Fb913CF7f9949C623F896a154727919", force=True)
    devProxyAdmin = accounts.at(
        "0x20Dce41Acca85E8222D6861Aa6D23B6C941777bF", force=True
    )

    controller = "0x9b4efA18c0c6b4822225b81D150f3518160f8609"  # Experimental
    badgerTree = "0x660802Fc641b154aBA66a62137e71f331B6d787A"

    # Deploy proxyAdmin
    proxyAdmin = deploy_proxy_admin(dev)
    proxyAdmin.transferOwnership(dualGovernance, {"from": dev})

    console.print("[green]ProxyAdmin was deployed at: [/green]", proxyAdmin.address)

    # Deploy voterProxy
    voterproxy = deploy_voterProxy(
        proxyAdmin, dev, dualGovernance, governance, strategist, keeper
    )

    # Deploy Vaults and Strategies
    strat_addresses = deploy_vaults_and_strategies(
        controller,
        governance,
        strategist,
        keeper,
        guardian,
        voterproxy,
        badgerTree,
        proxyAdmin,
        dev,
    )

    console.print("[green]Setting up voterproxy...: [/green]")

    for (key, address) in strat_addresses:
        if key == "native.mstableImBtc":
            vault = sett_config.native.imBtc.params.vault
        else:
            vault = sett_config.native.fPmBtcHBtc.params.vault
        voterproxy.supportStrategy(address, vault, {"from": dev})

    voterproxy.setGovernance(dualGovernance, {"from": dev})

    console.print("[green]Strategies supported and governance transferred [/green]")

    print("Balance of Dev: ", dev.balance())


def deploy_vaults_and_strategies(
    controller,
    governance,
    strategist,
    keeper,
    guardian,
    voterproxy,
    badgerTree,
    proxyAdmin,
    dev,
):
    strategies = []
    # Deploy Vaults and Strategies
    for (key, artifact) in [
        ("native.mstableImBtc", StrategyMStableVaultImbtc),
        ("native.mstableFpMbtcHbtc", StrategyMStableVaultFpMbtcHbtc),
    ]:
        if key == "native.mstableImBtc":
            params = sett_config.native.imBtc.params
            want = sett_config.native.imBtc.params.want
            strategy_logic = "0x663EfC293ca8d8DD6355AE6E99b71352BED9E895"
            vault_proxy = "0x599D92B453C010b1050d31C364f6ee17E819f193"
        else:
            params = sett_config.native.fPmBtcHBtc.params
            want = sett_config.native.fPmBtcHBtc.params.want
            strategy_logic = "0x5ddE67e4f0abD7a94E99C037A04A1946f9DbaA36"
            vault_proxy = "0x26B8efa69603537AC8ab55768b6740b67664D518"

        print("Deploying Vault and Strategy for " + key)

        # # Deploy Vault

        # args = [
        #     want,
        #     controller,
        #     governance.address,
        #     keeper.address,
        #     guardian.address,
        #     False,
        #     '',
        #     '',
        # ]

        # print("Vault Arguments: ", args)

        # vault_logic = SettV4.at("0xA762292A6A7fD944Db1Fe9389921e6F639B4C9E8") # SettV4 Logic
        # time.sleep(sleep_between_tx)

        # vault_proxy = AdminUpgradeabilityProxy.deploy(
        #     vault_logic,
        #     proxyAdmin,
        #     vault_logic.initialize.encode_input(*args),
        #     {'from': dev}
        # )
        # time.sleep(sleep_between_tx)

        # ## We delete from deploy and then fetch again so we can interact
        # AdminUpgradeabilityProxy.remove(vault_proxy)
        vault_proxy = SettV4.at(vault_proxy)

        console.print("[green]Vault was deployed at: [/green]", vault_proxy.address)

        assert vault_proxy.paused()

        # Deploy Strategy

        args = [
            governance.address,
            strategist.address,
            controller,
            keeper.address,
            guardian.address,
            [
                params.want,
                params.vault,
                voterproxy.address,
                params.lpComponent,
                badgerTree,
            ],
            [
                params.performanceFeeGovernance,
                params.performanceFeeStrategist,
                params.withdrawalFee,
                params.govMta,
            ],
        ]

        print("Strategy Arguments: ", args)

        strat_logic = artifact.at(strategy_logic)
        # strat_logic = artifact.deploy({"from": dev})
        # time.sleep(sleep_between_tx)
        # # Verify on Etherscan
        # # strat_logic.publish_source(artifact)

        strat_proxy = AdminUpgradeabilityProxy.deploy(
            strategy_logic,
            proxyAdmin,
            strat_logic.initialize.encode_input(*args),
            {"from": dev},
        )
        time.sleep(sleep_between_tx)

        ## We delete from deploy and then fetch again so we can interact
        AdminUpgradeabilityProxy.remove(strat_proxy)
        strat_proxy = artifact.at(strat_proxy.address)

        console.print("[green]Strategy was deployed at: [/green]", strat_proxy.address)

        strategies.append((key, strat_proxy.address))
    return strategies


def deploy_voterProxy(proxyAdmin, dev, dualGovernance, governance, strategist, keeper):
    # Deploy VoterProxy

    args = [
        dev.address,
        governance.address,
        strategist.address,
        keeper.address,
        [
            registry.mstable.nexus,
            registry.mstable.votingLockup,
        ],
        [8000],
    ]

    voterproxy_logic = MStableVoterProxy.deploy({"from": dev})
    time.sleep(sleep_between_tx)

    # Verify Contract
    # mstable.logic["MStableVoterProxy"].publish_source(MStableVoterProxy)

    voterproxy_proxy = AdminUpgradeabilityProxy.deploy(
        voterproxy_logic,
        proxyAdmin,
        voterproxy_logic.initialize.encode_input(*args),
        {"from": dev},
    )
    time.sleep(sleep_between_tx)

    ## We delete from deploy and then fetch again so we can interact
    AdminUpgradeabilityProxy.remove(voterproxy_proxy)
    voterproxy_proxy = MStableVoterProxy.at(voterproxy_proxy.address)

    console.print(
        "[green]VoterProxy was deployed at: [/green]", voterproxy_proxy.address
    )

    return voterproxy_proxy


def connect_account():
    click.echo(f"You are using the '{network.show_active()}' network")
    dev = accounts.load(click.prompt("Account", type=click.Choice(accounts.load())))
    click.echo(f"You are using: 'dev' [{dev.address}]")
    return dev
