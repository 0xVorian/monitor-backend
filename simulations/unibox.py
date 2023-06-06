class unibox:
    # btc_usd_price = $30k
    # flare_usd_price = $0.025

    # y is always btc

    def __init__(self,
                 initial_uni_btc_flare_x_in_usd,
                 initial_uni_usd_flare_x_in_usd):
        self.flare_btc_x = self.flare_btc_y = initial_uni_btc_flare_x_in_usd
        self.usd_btc_x = self.usd_btc_y = initial_uni_usd_flare_x_in_usd

    # static functions
    def _get_dy(self, x, y, dx):
        return y - x * y / (x + dx)

    def _get_dBTC(self, x_flare, y_flare, x_usd, y_usd, flare_in, usd_in):
        return self._get_dy(x_flare, y_flare, flare_in) + self._get_dy(x_usd, y_usd, usd_in)

    def _find_btc_liquidation_size(self, x_flare, y_flare, x_usd, y_usd, btc_in, flare_in, usd_in):
        min_btc = 0
        max_btc = btc_in
        curr_btc_in = max_btc  # be optimistic
        while True:
            curr_flare_in = flare_in * curr_btc_in / btc_in
            curr_usd_in = usd_in * curr_btc_in / btc_in

            out_btc = self._get_dBTC(x_flare, y_flare, x_usd, y_usd, curr_flare_in, curr_usd_in)
            if out_btc < curr_btc_in:
                max_btc = curr_btc_in
            else:
                min_btc = curr_btc_in

            # print(min_btc, max_btc)
            if ((min_btc > 0 and (max_btc / min_btc < 1.01)) or max_btc < 1e-08):
                obj = {"btc": min_btc, "usd": usd_in * min_btc / btc_in, "flare": flare_in * min_btc / btc_in}

                # print(self._get_dBTC(x_flare, y_flare, x_usd, y_usd, obj["flare"], obj["usd"]))
                return obj

            curr_btc_in = (min_btc + max_btc) / 2

    # public functions
    def update_prices(self, flare_usd_price, btc_usd_price):
        self.flare_usd_price = flare_usd_price
        self.btc_usd_price = btc_usd_price

    def find_btc_liquidation_size(self, btc_in, flare_in, usd_in):
        x_flare = self.flare_btc_x / self.flare_usd_price
        y_flare = self.flare_btc_y / self.btc_usd_price

        x_usd = self.usd_btc_x
        y_usd = self.usd_btc_y / self.btc_usd_price

        return self._find_btc_liquidation_size(x_flare, y_flare, x_usd, y_usd, btc_in, flare_in, usd_in)

    def dump_flare_to_btc(self, flare_in):
        dx = flare_in * self.flare_usd_price
        dy = self._get_dy(self.flare_btc_x, self.flare_btc_y, dx)

        self.flare_btc_x += dx
        self.flare_btc_y -= dy

        return dy

    def dump_usd_to_btc(self, usd_in):
        dx = usd_in
        dy = self._get_dy(self.usd_btc_x, self.usd_btc_y, dx)

        self.usd_btc_x += dx
        self.usd_btc_y -= dy

        return dy

    def recover_flare_liquidity(self, btc_in):
        dy = btc_in
        dx = self._get_dy(self.flare_btc_y, self.flare_btc_x, dy)

        self.flare_btc_x -= dx
        self.flare_btc_y += dy

    def recover_usd_liquidity(self, btc_in):
        dy = btc_in
        dx = self._get_dy(self.usd_btc_y, self.usd_btc_x, dy)

        self.usd_btc_x -= dx
        self.usd_btc_y += dy

    def get_flare_xy(self):
        return {"flare": self.flare_btc_x, "btc": self.flare_btc_y}

    def get_usd_xy(self):
        return {"usd": self.usd_btc_x, "btc": self.usd_btc_y}