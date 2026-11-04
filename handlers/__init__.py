from .commands import (
    join_cmd, start_cmd, salom_cmd, startgame_cmd, will_cmd, profile_cmd, balance_cmd, rating_cmd, guide_cmd, stop_cmd, chiqish_cmd, reveal_cmd,
    call_players_cmd, plan_cmd, boost_cmd, goal_cmd, teamwork_cmd, use_item_cmd
)
from .settings import settings_cmd
from .admin_panel import admin_cmd, stats_cmd
from .admin_ai import process_admin_ai_message
from .shop import shop_cmd, shop_callback_handler
from .clans import clan_cmd, newclan_cmd
from .social import (
    para_cmd, dpara_cmd, mypara_cmd, bro_cmd, dbro_cmd, mybro_cmd, givegul_cmd, send_cmd,
    coin_cmd, gold_cmd, givecoin_cmd, givegold_cmd
)
from .callbacks import callback_router
