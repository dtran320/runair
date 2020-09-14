from apscheduler.schedulers.blocking import BlockingScheduler

from rq import Queue
from worker import conn

from runair.poll_air_and_notify import poll_air_and_notify

NOTIFICATIION_GRANULARITY_MIN = 5

q = Queue(connection=conn)

sched = BlockingScheduler()


@sched.scheduled_job('interval', minutes=NOTIFICATIION_GRANULARITY_MIN)
def timed_job():
    print('This job is run every {} minutes.'.format(NOTIFICATIION_GRANULARITY_MIN))
    result = q.enqueue(poll_air_and_notify)
    print(result)


sched.start()