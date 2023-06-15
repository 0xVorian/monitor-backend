import utils
# utils.move_to_prod("aurigami", "2022-10-29-16-28")
# utils.move_to_prod("nervos", "2022-10-29-16-28")
# utils.move_to_prod("vesta", "2022-10-29-16-28")

utils.create_production_accounts_graph("0", "total_collateral", "Aurigami", "auUSDC")
utils.create_production_accounts_graph("0", "total_debt", "Aurigami", "auUSDC")

utils.create_production_accounts_graph("0", "total_collateral", "Aurigami", "auWBTC")
utils.create_production_accounts_graph("0", "total_debt", "Aurigami", "auWBTC")

utils.create_production_accounts_graph("0", "total_collateral", "Aurigami")
utils.create_production_accounts_graph("0", "total_debt", "Aurigami")

utils.create_production_accounts_graph("2", "total_collateral", "Vesta")
utils.create_production_accounts_graph("2", "total_debt", "Vesta")

utils.create_production_slippage_graph("0", "Aurigami")
utils.create_production_slippage_graph("2", "Vesta")

