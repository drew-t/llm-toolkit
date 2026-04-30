import asyncio

import pytest

from llm_toolkit.jobs.broadcaster import Broadcaster
from llm_toolkit.jobs.events import JobEvent


@pytest.mark.asyncio
async def test_subscriber_receives_published_events():
    bc = Broadcaster()
    sub = bc.subscribe()
    await bc.publish(JobEvent.log("hi"))
    e = await asyncio.wait_for(sub.get(), timeout=0.5)
    assert e.type == "log"
    assert e.payload["line"] == "hi"


@pytest.mark.asyncio
async def test_two_subscribers_both_receive():
    bc = Broadcaster()
    a, b = bc.subscribe(), bc.subscribe()
    await bc.publish(JobEvent.status("running"))
    ea = await asyncio.wait_for(a.get(), timeout=0.5)
    eb = await asyncio.wait_for(b.get(), timeout=0.5)
    assert ea.type == eb.type == "status"


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery():
    bc = Broadcaster()
    sub = bc.subscribe()
    bc.unsubscribe(sub)
    await bc.publish(JobEvent.log("ignored"))
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(sub.get(), timeout=0.05)


@pytest.mark.asyncio
async def test_close_signals_subscribers_with_none():
    bc = Broadcaster()
    sub = bc.subscribe()
    await bc.close()
    sentinel = await asyncio.wait_for(sub.get(), timeout=0.5)
    assert sentinel is None


@pytest.mark.asyncio
async def test_slow_subscriber_dropped_when_buffer_full():
    bc = Broadcaster(max_queue=2)
    sub = bc.subscribe()
    await bc.publish(JobEvent.log("a"))
    await bc.publish(JobEvent.log("b"))
    await bc.publish(JobEvent.log("c"))
    assert sub not in bc._subs
