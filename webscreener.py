import asyncio
import gc
import os
import traceback

import aiohttp
from arsenic import get_session
from arsenic.browsers import Chrome
from arsenic.services import Chromedriver
from quart import Quart, jsonify, request

app = Quart(__name__)
maincache = str()
with open("main.html", "r") as f:
    maincache = f.read()
ratelimits = dict()

service = Chromedriver(log_file=os.devnull)
browser = Chrome(
    chromeOptions={
        "args": [
            "--headless",
            "--hide-scrollbars",
            #"--no-gpu"
            #"--disable-gpu"
            "--window-size=1366,768",
            "--ipc-connection-timeout=10",
            "--max_old_space_size=20",
            "--disable-mojo-local-storage",
            ]
        }
    )

async def make_snapshot(website: str):
    async with get_session(service, browser) as session:
        await session.get(website)
        image = await session.get_screenshot()
        image.seek(0)

        async with aiohttp.ClientSession() as sess:

            headers = {"Authorization": "Client-ID 6656d64547a5031"}
            data = {"image": image}

            async with sess.post(
                "https://api.imgur.com/3/image", data=data, headers=headers
            ) as r:
                link = (await r.json())["data"]["link"]

                gc.collect()
                
                del image
                del sess
                
                return link


@app.route("/")
async def main():
    return maincache

@app.route("/api/v1", methods=["POST"])
@app.route("/v1", methods=["POST"])
async def web_screenshot():

    website = request.headers.get("website")

    if website is None:
        return jsonify(
            {
                "snapshot": "https://cdn1.iconfinder.com/data/icons/web-interface-part-2/32/circle-question-mark-512.png",
                "website": "A website was not provided.",
                "status": 400,
            }
        )

    if not (website.startswith("http://") or website.startswith("https://")):
        website = f"http://{website}"

    ip = request.remote_addr
    try:
        ratelimits[ip]
    except KeyError:
        ratelimits[ip] = 1
    else:
        if ratelimits[ip] >= 5:
            await asyncio.sleep(5)
            ratelimits[ip] = 0
        ratelimits[ip] += 1
    link = await make_snapshot(website)

    try:
        
        return jsonify({"snapshot": link, 
                        "website": website, 
                        "status": 200, 
                       })
    except Exception:
        return traceback.format_exc()

app.run(host="0.0.0.0", port=os.getenv("PORT"))
