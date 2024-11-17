import logging
import os
import sys
import shutil
import config
import asyncio
from pyrogram import Client, filters
from pyrogram.errors.exceptions.bad_request_400 import AccessTokenInvalid
from pyrogram.types import BotCommand
from config import API_HASH, API_ID, OWNER_ID
from nexichat import CLONE_OWNERS
from nexichat import nexichat as app, save_clonebot_owner
from nexichat import db as mongodb

IDCLONES = set()
cloneownerdb = mongodb.cloneownerdb
clonebotdb = mongodb.clonebotdb


@app.on_message(filters.command(["idclone"]))
async def clone_txt(client, message):
    if len(message.command) > 1:
        string_session = message.text.split("/idclone", 1)[1].strip()
        mi = await message.reply_text("**Checking your String Session...**")
        try:
            ai = Client(
                name="VIPIDCHATBOT",
                api_id=config.API_ID,
                api_hash=config.API_HASH,
                session_string=str(string_session),
                no_updates=False,
                plugins=dict(root="nexichat.idchatbot"),
            )
            await ai.start()
            user = await ai.get_me()
            user_id = user.id
            username = user.username or user.first_name
            await save_clonebot_owner(user_id, message.from_user.id)
            
            details = {
                "user_id": user.id,
                "username": username,
                "name": user.first_name,
                "session": string_session,
            }

            cloned_bots = clonebotdb.find()
            cloned_bots_list = await cloned_bots.to_list(length=None)
            total_clones = len(cloned_bots_list)

            await app.send_message(
                int(OWNER_ID), f"**#New_Clone**\n\n**User:** @{username}\n\n**Details:** {details}\n\n**Total Clones:** {total_clones}"
            )

            await clonebotdb.insert_one(details)
            IDCLONES.add(user.id)

            await mi.edit_text(
                f"**Session for @{username} successfully cloned ✅.**\n"
                f"**Remove clone by:** /delclone\n**Check all cloned sessions by:** /cloned"
            )
        except AccessTokenInvalid:
            await mi.edit_text("**Invalid String Session. Please provide a valid one.**")
        except Exception as e:
            logging.exception("Error during cloning process.")
            await mi.edit_text(f"**Error:** `{e}`")
    else:
        await message.reply_text("**Provide a String Session after the /idclone command.**")


@app.on_message(filters.command("idcloned"))
async def list_cloned_sessions(client, message):
    try:
        cloned_bots = clonebotdb.find()
        cloned_bots_list = await cloned_bots.to_list(length=None)
        if not cloned_bots_list:
            await message.reply_text("**No sessions have been cloned yet.**")
            return

        total_clones = len(cloned_bots_list)
        text = f"**Total Cloned Sessions:** {total_clones}\n\n"
        for bot in cloned_bots_list:
            text += f"**User ID:** `{bot['user_id']}`\n"
            text += f"**Name:** {bot['name']}\n"
            text += f"**Username:** @{bot['username']}\n\n"

        await message.reply_text(text)
    except Exception as e:
        logging.exception(e)
        await message.reply_text("**An error occurred while listing cloned sessions.**")


@app.on_message(
    filters.command(["delclone", "deleteclone", "removeclone"])
)
async def delete_cloned_session(client, message):
    try:
        if len(message.command) < 2:
            await message.reply_text("**⚠️ Please provide the session string after the command.**")
            return

        string_session = " ".join(message.command[1:])
        ok = await message.reply_text("**Checking the session string...**")

        cloned_session = await clonebotdb.find_one({"session": string_session})
        if cloned_session:
            await clonebotdb.delete_one({"session": string_session})
            IDCLONES.remove(cloned_session["user_id"])

            await ok.edit_text(
                f"**Session for `{cloned_session['username']}` has been removed from my database ✅.**"
            )
        else:
            await message.reply_text("**⚠️ The provided session is not in the cloned list.**")
    except Exception as e:
        await message.reply_text(f"**An error occurred while deleting the cloned session:** {e}")
        logging.exception(e)


@app.on_message(filters.command("delallclone") & filters.user(int(OWNER_ID)))
async def delete_all_cloned_sessions(client, message):
    try:
        a = await message.reply_text("**Deleting all cloned sessions...**")
        await clonebotdb.delete_many({})
        IDCLONES.clear()
        await a.edit_text("**All cloned sessions have been deleted successfully ✅**")
    except Exception as e:
        await a.edit_text(f"**An error occurred while deleting all cloned sessions:** {e}")
        logging.exception(e)



async def restart_idchatbots():
    global IDCLONES
    try:
        logging.info("Restarting all cloned sessions...")
        sessions = [session async for session in clonebotdb.find()]
        
        async def restart_session(session):
            string_session = session["session"]
            ai = Client(
                name="VIPIDCHATBOT",
                api_id=config.API_ID,
                api_hash=config.API_HASH,
                session_string=str(string_session),
                no_updates=False,
                plugins=dict(root="nexichat.idchatbot"),
            )
            try:
                await ai.start()
                user = await ai.get_me()
                
                if user.id not in IDCLONES:
                    IDCLONES.add(user.id)

                logging.info(f"Successfully restarted session for: @{user.username or user.first_name}")
            except Exception as e:
                logging.exception(f"Error while restarting session for: {session['username']}. Removing invalid session.")
                await clonebotdb.delete_one({"session": string_session})

        await asyncio.gather(*(restart_session(session) for session in sessions))

        logging.info("All sessions restarted successfully.")
    except Exception as e:
        logging.exception("Error while restarting sessions.")
