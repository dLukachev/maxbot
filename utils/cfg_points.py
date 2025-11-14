import asyncio
import configparser

from core.database.requests import TargetCRUD, SessionCRUD, UserCRUD
from datetime import datetime, timedelta

config = configparser.ConfigParser()

def get_levels_config(config_path="config.ini"):
    config.read(config_path, encoding='utf-8-sig')
    return dict(config["levels"])

async def check_level(user_id) -> bool:
    user = await UserCRUD.get_by_tid(user_id)
    if not user:
        print(f"ERROR {user}")
        return False

    levels_cfg = get_levels_config()
    if not levels_cfg:
        print(f"ERROR lvl cfg{levels_cfg}")
        return False

    sorted_thresholds = sorted(levels_cfg.keys())
    new_level = user.level

    # Пройдемся по порогам и найдем максимальный достигнутый уровень
    for threshold in sorted_thresholds:
        if user.points >= int(threshold):
            candidate_level = levels_cfg[threshold]
            if candidate_level > new_level:
                new_level = candidate_level
        else:
            break

    if new_level != user.level:
        await UserCRUD.update(user_id=user_id, level=new_level)

    return True

def xyz(total_target, count_done_target, boost):
    """
    total_target - всего целей
    count_done_target - кол-во сделанных целей
    boost - коэф в формуле (чем больше значение, тем больше понитов)
    """
    return int((count_done_target / total_target) * 3 * boost)

async def calculate_points_and_level(user_id: int) -> None:
    """Производит расчет поинтов и обновление уровня, если поинтов достаточно
    Args: user_id"""
    # if time_work > 3 hours + 2 points
    # count add point = formula()
    # if not target = -10 points

    # in SessionCRUD.list_by_user_on_date(user_id, datetime.now()) we can
    # check all session on today

    # in TargetCRUD.get_all_target_today(user_id, datetime.now()) we can see
    # all target today

    try:
        _, targets = await TargetCRUD.get_all_target_today(user_id, datetime.today())
    except Exception as e:
        print(f"ERROR {e}")
        return

    action_points = 0

    if len(targets) == 0:
        action_points = -10
        print(action_points)
        await UserCRUD.points(user_id, action_points)
        return
    else:
        session = await SessionCRUD.total_active_time_on_date(user_id, datetime.now())
        if session > timedelta(hours=3):
            action_points = 3

    boost = 0.6314
    count_done_target = 0
    total_target = len(targets)
    for target in targets:
        if target.is_done:
            count_done_target += 1

    action_points += xyz(total_target, count_done_target, boost)
    await UserCRUD.points(user_id, action_points)
    if await check_level(user_id):
        print("SUCCESS check_level")
    else:
        print("ERROR check_level")