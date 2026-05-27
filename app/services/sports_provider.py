class SportsDataProvider:
    def get_live_games(self, league):
        raise NotImplementedError

    def get_game_details(self, external_game_id):
        raise NotImplementedError
