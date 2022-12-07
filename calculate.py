#!/usr/bin/env python3

import click
import configparser
import pprint
import readchar
import requests
import signal
import sys
import time

from pathlib import Path
from nicehash import nicehash

# A cheap way to lookup the values for wtm profitability requests
wtm_query_map = {
    "sha256": "sha256f=true&factor%5Bsha256_hr%5D=1000000.0&factor%5Bsha256_p%5D=0.0",
    "scrypt": "scryptf=true&factor%5Bscrypt_hash_rate%5D=0.205&factor%5Bscrypt_power%5D=220.0",
    "x11": "x11f=true&factor%5Bx11_hr%5D=1286.0&factor%5Bx11_p%5D=3148.0",
    "sia": "siaf=true&factor%5Bsia_hr%5D=17.0&factor%5Bsia_p%5D=3300.0",
    "quark": "qkf=true&factor%5Bqk_hr%5D=28.0&factor%5Bqk_p%5D=800.0",
    "qubit": "qbf=true&factor%5Bqb_hr%5D=28.0&factor%5Bqb_p%5D=850.0",
    "myr-groestl": "mgf=true&factor%5Bmg_hr%5D=28.0&factor%5Bmg_p%5D=350.0",
    "skein": "skf=true&factor%5Bsk_hr%5D=14.0&factor%5Bsk_p%5D=300.0",
    "lbry": "lbryf=true&factor%5Blbry_hr%5D=1620.0&factor%5Blbry_p%5D=1450.0",
    "blake": "bk14f=true&factor%5Bbk14_hr%5D=52.0&factor%5Bbk14_p%5D=2200.0",
    "cryptonight": "cnf=true&factor%5Bcn_hr%5D=360.0&factor%5Bcn_p%5D=720.0",
    "cryptonightstc": "cstf=true&factor%5Bcst_hr%5D=13.9&factor%5Bcst_p%5D=65.0",
    "equihash": "eqf=true&factor%5Beq_hr%5D=420.0&factor%5Beq_p%5D=1510.0",
    "lyra2rev2": "lrev2f=true&factor%5Blrev2_hr%5D=13.0&factor%5Blrev2_p%5D=1100.0",
    "bcd": "bcdf=true&factor%5Bbcd_hr%5D=278.0&factor%5Bbcd_p%5D=708.0",
    "lyra2z": "l2zf=true&factor%5Bl2z_hr%5D=93.0&factor%5Bl2z_p%5D=708.0",
    "keccak": "kecf=true&factor%5Bkec_hr%5D=34.9&factor%5Bkec_p%5D=708.0",
    "groestl": "grof=true&factor%5Bgro_hr%5D=28.0&factor%5Bgro_p%5D=450.0",
    "eaglesong": "esgf=true&factor%5Besg_hr%5D=1050.0&factor%5Besg_p%5D=215.0",
    "cuckatoo31": "ct31f=true&factor%5Bct31_hr%5D=126.0&factor%5Bct31_p%5D=2800.0",
    "cuckatoo32": "ct32f=true&factor%5Bct32_hr%5D=36.0&factor%5Bct32_p%5D=2800.0",
    "kadena": "kdf=true&factor%5Bkd_hr%5D=40.2&factor%5Bkd_p%5D=3350.0",
    "handshake": "hkf=true&factor%5Bhk_hr%5D=4.3&factor%5Bhk_p%5D=3250.0",
}


def sighandler(signum, frame):
    sys.exit(0)


def get_nh_data(algorithm):
    nh_algos = (
        requests.get("https://api2.nicehash.com/main/api/v2/mining/algorithms")
        .json()
        .get("miningAlgorithms")
    )
    algo_positions = [i.get("algorithm") for i in nh_algos]
    req_data = []
    if len(algorithm) == 0:
        click.secho("Available algorithms:", bold=True, fg="green")
        for i in algo_positions:
            click.secho(f"  - {i}", fg="green")
        sys.exit(0)
    for algo in algorithm:
        algo = algo.upper()
        req_data.append(nh_algos[algo_positions.index(algo)])
    return req_data


def get_nh_wtm_data(algorithm, coin_filter):
    req_base = "https://whattomine.com/asic.json?"
    query = wtm_query_map.get(algorithm.lower())
    # There's a bunch of other params we don't both adjusting with flags yet, just jam them in here for now
    boilerplate_params = "factor%5Bcost%5D=0.1&factor%5Bcost_currency%5D=USD&sort=Profit&volume=0&revenue=24hfactor%5Bexchanges%5D%5B%5D=binance&dataset=Main"

    raw_data = (
        requests.get(req_base + query + "&" + boilerplate_params).json().get("coins")
    )
    coins = raw_data.keys()
    rev_sum = 0.0
    for i in coin_filter:
        for c in coins:
            if i.upper() in raw_data.get(c).get("tag"):
                rev_sum += float(raw_data.get(c).get("btc_revenue24"))

    return rev_sum


def get_optimal(algo):
    return (
        requests.get(
            f"https://api2.nicehash.com/main/api/v2/hashpower/order/price?market=USA&algorithm={algo}"
        )
        .json()
        .get("price")
    )


def raise_order(private_api, order_id, new_price, order_limit, order_algo, nh_algos):
    try:
        private_api.set_price_and_limit_hashpower_order(
            order_id, new_price, order_limit, order_algo, nh_algos
        )
    except Exception as e:
        e = str(e)


signal.signal(signal.SIGINT, sighandler)


@click.command()
@click.option(
    "--algorithm", "-a", "algorithm", default=None, multiple=True, required=True
)
@click.option(
    "--coin", "-c", "coin", required=False, default=["nicehash"], multiple=True
)
# The way we're implementing the watch flag feels like a hack
# It is an optional arg that, if not provided, has a value of 0 which is interpreted as "don't loop"
# But if you provide the -w flag it then gets a "default" value of 5 unless you provide your own integer
# after the flag (eg. `-w` would use a value of 5 and `-w 10` would use a value of 10.)
@click.option("--watch", "-w", is_flag=False, flag_value=5, default=0)
@click.option("--config", "config_file", required=False, default="./config.ini")
@click.option("--manage", "-m", is_flag=True, required=False)
def run(algorithm, coin, watch, config_file, manage):

    # Check config path exists
    config = Path(config_file)
    if not config.is_file():
        click.secho(f"{config} does not exist.", bold=True, fg="red")
        sys.exit(1)

    # Parse the config since we know it exists
    config = configparser.ConfigParser()
    config.read(config_file)

    # Create private API interface
    # Also, I hate the nicehash python library. No auth validation on the client instance, smh
    # After we make `private_api` we won't know if the credentials are good until the first time we use it
    # And even then we'll only get a 404 so like... idgaf, just make sure your stuff is right in the config
    private_api = nicehash.private_api(
        config["DEFAULT"]["host"],
        config["DEFAULT"]["organization_id"],
        config["DEFAULT"]["key"],
        config["DEFAULT"]["secret"],
    )

    managed_orders = config.sections()
    rounds_out_of_profit = 0

    seconds_with_work = 0
    seconds_without_work = 0
    # Artificially slow down the rate of raising our order price to be more in-line with the speed at which we can
    # lower it again. This should help smooth out spikes but we might need to make this a user parameter in the future
    without_work_threshold = 600

    # Nicehash only allows us to lower the price once every 10 minutes
    cooldown = 0

    while True:
        out_width_array = []
        # Get the Nicehash data about the algorithms requested
        nh_data = get_nh_data(algorithm)

        # Loop through the returned algo data and process each algo
        for i in nh_data:
            # Get the optimal order price for our algo and cast it to a float
            optimal = float(get_optimal(i.get("algorithm")))

            # Get the current profitability from WTM for the same algo and cast it to a float too
            wtm_profitability = float(get_nh_wtm_data(i.get("algorithm"), coin))

            # Print the optimal, profitability
            msg = f"Optimal: {optimal}"
            out_width_array.append(len(msg))
            print(msg)
            msg = f"Profit/GH: {wtm_profitability}"
            out_width_array.append(len(msg))
            print(msg)

            # Calculate Expected profit percentage and print that too
            perc_profit = round((1 - (optimal / wtm_profitability)) * 100, 2)
            if perc_profit > 0.0:
                color = "green"
                rounds_out_of_profit = 0
            else:
                color = "red"
                rounds_out_of_profit += 1
            msg = f"Theoretical Profit: {perc_profit}%"
            print(str(rounds_out_of_profit * watch) + " seconds out of profit")
            out_width_array.append(len(msg))
            click.secho(msg, fg=color)

        if len(managed_orders) > 0 and manage:
            for order_id in managed_orders:
                if not config.getboolean(order_id, "manage"):
                    continue
                order_details = private_api.request(
                    # Get the order details (requires manual request using private_api)
                    "GET",
                    f"/main/api/v2/hashpower/order/{order_id}",
                    "",
                    "",
                )

                # Further sanity check that the order is active
                if order_details.get("status").get("code") != "ACTIVE":
                    continue

                order_price = float(order_details.get("price"))
                order_algo = order_details.get("algorithm").get("algorithm")
                order_limit = order_details.get("limit")
                msg = f"Current Order Price: {order_price}"
                out_width_array.append(len(msg))
                print(msg)
                exp_perc_profit = round(
                    (1 - (order_price / wtm_profitability)) * 100, 2
                )
                msg = f"Expected Profit: {exp_perc_profit}%"
                out_width_array.append(len(msg))
                print(msg)
                nh_algos = requests.get(
                    "https://api2.nicehash.com/main/api/v2/mining/algorithms"
                ).json()
                buy_info = requests.get(
                    "https://api2.nicehash.com/main/api/v2/public/buy/info"
                ).json()
                for i in buy_info.get("miningAlgorithms"):
                    if i.get("name").upper() == order_algo:
                        step = abs(float(i.get("down_step")))
                        break

                accepted_speed = float(order_details.get("acceptedCurrentSpeed"))

                # Check if order is lower than optimal and lower than profitability
                # Raise the price to be closer to optimal if it's below it
                if (
                    order_price < optimal and accepted_speed == 0.0
                ) and order_price < wtm_profitability:
                    new_price = round(order_price + step, 4)
                    msg = f"Calculated new price: {new_price}"
                    out_width_array.append(len(msg))
                    print(msg)
                    if new_price < wtm_profitability:
                        raise_order(
                            private_api,
                            order_id,
                            new_price,
                            order_limit,
                            order_algo,
                            nh_algos,
                        )

                # If the order price goes above the profitable, try to lower it and start a counter to cancel it (not yet implemented)
                if (
                    order_price > wtm_profitability
                    or order_price > optimal
                    and cooldown == 0
                ):
                    try:
                        private_api.set_price_and_limit_hashpower_order(
                            order_id,
                            round(order_price - step, 4),
                            order_limit,
                            order_algo,
                            nh_algos,
                        )
                    except Exception as e:
                        cooldown = int(str(e).split(" ")[-1].split('"')[0]) + 1
                        out_width_array.append(len(msg))

                # If we have an order that's in profit but have waited the "without_work_threshold"
                # duration and still have no accepted work, raise the price
                if (
                    order_price < wtm_profitability
                    and exp_perc_profit > perc_profit
                    and seconds_without_work > without_work_threshold
                ):
                    new_price = round(order_price + step, 4)
                    msg = f"Calculated new price: {new_price}"
                    out_width_array.append(len(msg))
                    print(msg)
                    if new_price < wtm_profitability:
                        raise_order(
                            private_api,
                            order_id,
                            new_price,
                            order_limit,
                            order_algo,
                            nh_algos,
                        )

                    seconds_without_work = 0

                if (
                    order_price < wtm_profitability
                    and exp_perc_profit < perc_profit
                    and seconds_with_work > 300
                    and cooldown == 0
                ):
                    new_price = round(order_price - step, 4)
                    msg = f"Calculated new price: {new_price}"

                    out_width_array.append(len(msg))
                    print(msg)
                    if new_price < wtm_profitability:
                        raise_order(
                            private_api,
                            order_id,
                            new_price,
                            order_limit,
                            order_algo,
                            nh_algos,
                        )

                    seconds_with_work = 0
                    cooldown = 600

        if accepted_speed == 0.0:
            seconds_without_work += watch
            seconds_with_work = 0
            print(accepted_speed)
            print(
                f"{seconds_without_work} seconds since we've had accepted shares, will increase order price in {without_work_threshold - seconds_without_work} seconds"
            )
        else:
            seconds_without_work = 0
            seconds_with_work += watch
            print(f"Work accepted for {seconds_with_work} seconds at current price")
            print(f"Cooldown Remaining: {cooldown}s")

        cooldown -= watch

        print("-" * max(out_width_array))
        if watch:
            time.sleep(watch)

        if watch == 0:
            signal.raise_signal(signal.SIGINT)


if __name__ == "__main__":
    run()
