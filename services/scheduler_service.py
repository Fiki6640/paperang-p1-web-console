#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时任务服务模块
使用 APScheduler 管理定时任务
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


class SchedulerService:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        self.jobs = {}
        logging.info("Scheduler service started")

    def add_daily_job(self, job_id, hour, minute, func, *args, **kwargs):
        if job_id in self.jobs:
            self.remove_job(job_id)
        
        trigger = CronTrigger(hour=hour, minute=minute)
        job = self.scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            args=args,
            kwargs=kwargs,
            replace_existing=True
        )
        self.jobs[job_id] = {
            "job": job,
            "hour": hour,
            "minute": minute,
            "enabled": True
        }
        logging.info("Added daily job '%s' at %02d:%02d" % (job_id, hour, minute))
        return job

    def remove_job(self, job_id):
        if job_id in self.jobs:
            try:
                self.scheduler.remove_job(job_id)
            except Exception as e:
                logging.error("Failed to remove job %s: %s" % (job_id, str(e)))
            del self.jobs[job_id]
            logging.info("Removed job '%s'" % job_id)

    def pause_job(self, job_id):
        if job_id in self.jobs:
            try:
                self.scheduler.pause_job(job_id)
                self.jobs[job_id]["enabled"] = False
                logging.info("Paused job '%s'" % job_id)
            except Exception as e:
                logging.error("Failed to pause job %s: %s" % (job_id, str(e)))

    def resume_job(self, job_id):
        if job_id in self.jobs:
            try:
                self.scheduler.resume_job(job_id)
                self.jobs[job_id]["enabled"] = True
                logging.info("Resumed job '%s'" % job_id)
            except Exception as e:
                logging.error("Failed to resume job %s: %s" % (job_id, str(e)))

    def get_job_status(self, job_id):
        if job_id not in self.jobs:
            return None
        job_info = self.jobs[job_id]
        return {
            "id": job_id,
            "hour": job_info["hour"],
            "minute": job_info["minute"],
            "enabled": job_info["enabled"],
            "next_run_time": str(job_info["job"].next_run_time) if job_info["job"].next_run_time else None
        }

    def get_all_jobs(self):
        return [self.get_job_status(jid) for jid in self.jobs]

    def shutdown(self):
        self.scheduler.shutdown()
        logging.info("Scheduler service stopped")
