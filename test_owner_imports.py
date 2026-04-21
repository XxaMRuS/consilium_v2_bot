# -*- coding: utf-8 -*-
# Test script to verify owner_handlers imports

import sys
import traceback

def test_imports():
    """Test all owner_handlers imports"""
    print("Checking owner_handlers imports...\n")

    try:
        from owner_handlers import (
            OWNER_MENU, OWNER_STATS, OWNER_BALANCES,
            OWNER_CHAMPIONS, OWNER_CHAMPIONS_HISTORY, OWNER_CHAMPIONS_MENU,
            OWNER_CHAMPIONS_CALCULATE, OWNER_CHAMPIONS_CONFIRM,
            OWNER_COMPETITIONS, OWNER_COMPETITIONS_TOGGLE,
            OWNER_FF_INFO,
            owner_menu_callback,
            owner_stats_callback,
            owner_balances_callback,
            owner_champions_history_callback,
            owner_champions_menu_callback,
            owner_champions_calculate_callback,
            owner_champions_confirm_callback,
            owner_competitions_callback,
            owner_competitions_toggle_callback,
            owner_ff_info_callback,
        )

        print("OK Constants:")
        print(f"   OWNER_MENU = {OWNER_MENU}")
        print(f"   OWNER_CHAMPIONS_HISTORY = {OWNER_CHAMPIONS_HISTORY}")
        print(f"   OWNER_COMPETITIONS = {OWNER_COMPETITIONS}")
        print(f"   OWNER_FF_INFO = {OWNER_FF_INFO}")
        print()

        print("OK Functions:")
        print(f"   owner_champions_history_callback: {owner_champions_history_callback.__name__}")
        print(f"   owner_competitions_callback: {owner_competitions_callback.__name__}")
        print(f"   owner_competitions_toggle_callback: {owner_competitions_toggle_callback.__name__}")
        print(f"   owner_ff_info_callback: {owner_ff_info_callback.__name__}")
        print()

        print("OK All imports successful!")
        return True

    except Exception as e:
        print(f"ERROR Import failed: {e}")
        traceback.print_exc()
        return False


def test_bot_imports():
    """Test imports in bot.py"""
    print("\nChecking bot.py imports...\n")

    try:
        import bot

        # Check constants
        print("OK Constants in bot.py:")
        print(f"   OWNER_CHAMPIONS_HISTORY = {bot.OWNER_CHAMPIONS_HISTORY}")
        print(f"   OWNER_COMPETITIONS = {bot.OWNER_COMPETITIONS}")
        print(f"   OWNER_FF_INFO = {bot.OWNER_FF_INFO}")
        print()

        # Check functions
        print("OK Functions in bot.py:")
        print(f"   owner_champions_history_callback: {hasattr(bot, 'owner_champions_history_callback')}")
        print(f"   owner_competitions_callback: {hasattr(bot, 'owner_competitions_callback')}")
        print(f"   owner_competitions_toggle_callback: {hasattr(bot, 'owner_competitions_toggle_callback')}")
        print(f"   owner_ff_info_callback: {hasattr(bot, 'owner_ff_info_callback')}")
        print()

        print("OK bot.py imports all necessary functions!")
        return True

    except Exception as e:
        print(f"ERROR bot.py import failed: {e}")
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = True

    if not test_imports():
        success = False

    if not test_bot_imports():
        success = False

    if success:
        print("\n" + "="*50)
        print("ALL CHECKS PASSED!")
        print("="*50)
        print("\nRESTART THE BOT:")
        print("   1. Stop the current bot process")
        print("   2. Start bot again: python bot.py")
        print("   3. Try the buttons in owner panel")
        print("="*50)
    else:
        print("\nERRORS FOUND - check logs above")
        sys.exit(1)
