from tests.sett.fixtures.SettMiniDeployBase import SettMiniDeployBase
from config.badger_config import sett_config
from helpers.token_utils import distribute_from_whales
from brownie import *
from helpers.proxy_utils import deploy_proxy


class ConvexPBtcMiniDeploy(SettMiniDeployBase):
    def fetch_params(self):
        params = sett_config.native.convexPbtcCrv.params
        want = sett_config.native.convexPbtcCrv.params.want

        params.badgerTree = self.badger.badgerTree

        return (params, want)

    def post_vault_deploy_setup(self, deploy=True):
        if not deploy:
            return
        distribute_from_whales(self.deployer, 1)

    def post_deploy_setup(self, deploy):
        if deploy:
            return

        if not (self.vault.controller() == self.strategy.controller()):
            # NB: Not all vaults are pauseable.
            try:
                if self.vault.paused():
                    self.vault.unpause({"from": self.governance})
            except exceptions.VirtualMachineError:
                pass
            # Change vault's conroller to match the strat's
            self.vault.setController(
                self.strategy.controller(), {"from": self.governance}
            )

        # Check that vault's and Strat's controller is the same
        assert self.vault.controller() == self.strategy.controller()

        # Check that want is the same for vault and strategy
        assert self.vault.token() == self.strategy.want()

        self.controller = interface.IController(self.vault.controller())

        # The timelock is th assigned governance address for the vault and strategy
        timelock = accounts.at("0x21CF9b77F88Adf8F8C98d7E33Fe601DC57bC0893", force=True)

        # Add strategy to controller for want
        self.controller.approveStrategy(
            self.strategy.want(), self.strategy.address, {"from": self.governance}
        )
        self.controller.setStrategy(
            self.strategy.want(), self.strategy.address, {"from": self.governance}
        )

        # Add vault to controller for want
        # self.controller.setVault(self.vault.token(), self.vault.address, {"from": self.governance})

        assert self.controller.strategies(self.vault.token()) == self.strategy.address
        assert self.controller.vaults(self.strategy.want()) == self.vault.address

        # Add actors to guestlist
        guestlist = VipCappedGuestListBbtcUpgradeable.at(self.vault.guestList())

        addresses = []
        for account in accounts:
            addresses.append(account.address)

        # Add actors addresses
        addresses.append(guestlist.owner())
        addresses.append(self.governance.address)
        addresses.append(self.strategist.address)
        addresses.append(self.keeper.address)
        addresses.append(self.guardian.address)
        addresses.append(self.deployer.address)

        invited = [True] * len(addresses)

        guestlist.setGuests(addresses, invited, {"from": self.deployer})

    # Setup used for running simulation without deployed strategy:

    # def post_deploy_setup(self, deploy):
    #     if deploy:
    #         return

    #     (params, want) = self.fetch_params()

    #     self.controller = interface.IController(self.vault.controller())

    #     contract = StrategyConvexStakingOptimizer.deploy({"from": self.deployer})
    #     self.strategy = deploy_proxy(
    #         "StrategyConvexStakingOptimizer",
    #         StrategyConvexStakingOptimizer.abi,
    #         contract.address,
    #         web3.toChecksumAddress(self.badger.devProxyAdmin.address),
    #         contract.initialize.encode_input(
    #             self.governance.address,
    #             self.strategist.address,
    #             self.controller.address,
    #             self.keeper.address,
    #             self.guardian.address,
    #             [params.want, self.badger.badgerTree,],
    #             params.pid,
    #             [
    #                 params.performanceFeeGovernance,
    #                 params.performanceFeeStrategist,
    #                 params.withdrawalFee,
    #             ],
    #         ),
    #         self.deployer,
    #     )

    #     self.badger.sett_system.strategies[self.key] = self.strategy

    #     assert self.controller.address == self.strategy.controller()

    #     self.controller.approveStrategy(self.strategy.want(), self.strategy.address, {"from": self.governance})
    #     self.controller.setStrategy(self.strategy.want(), self.strategy.address, {"from": self.governance})

    #     assert self.controller.strategies(self.vault.token()) == self.strategy.address