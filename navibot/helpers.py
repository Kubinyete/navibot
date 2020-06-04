import asyncio
import time

class TimeoutContext:
    def __init__(self, waitfor: int, callable: callable, callback: callable=None, **kwargs):
        self.waitfor = waitfor
        self.callable = callable
        self.callback = callback
        self.kwargs = kwargs
        self.running_task = None

    async def run(self):
        try:
            await asyncio.sleep(self.waitfor)
            await self.callable(self, self.kwargs)

            if self.callback:
                await self.callback(self, self.kwargs)
        except Exception as e:
            raise e
        finally:
            self.running_task = None

    def create_task(self):
        assert not self.is_running()
        self.running_task = asyncio.create_task(self.run())

    def cancel_task(self):
        assert self.is_running()
        return self.running_task.cancel()

    def is_running(self):
        return self.running_task is not None

class IntervalContext(TimeoutContext):
    def __init__(self, waitfor: int, callable: callable, max_count: int=0, callback: callable=None, ignore_exception: bool=False, **kwargs):
        super().__init__(waitfor, callable, callback=callback, **kwargs)
        self.ignore_exception = ignore_exception
        self.max_count = max_count
        self.safe_halt = False
        self.run_count = 0
    
    async def run(self):
        time_start = 0
        time_delta = 0

        try:
            while not self.safe_halt and (self.max_count <= 0 or self.run_count < self.max_count):
                time_start = time.time()
                
                try:
                    self.run_count += 1
                    await self.callable(self, self.kwargs)
                except Exception as e:
                    if not self.ignore_exception:
                        raise e
                finally:
                    time_delta = time.time() - time_start
                    await asyncio.sleep(self.waitfor - time_delta)    
        except Exception as e:
            raise e
        finally:
            self.running_task = None

            if self.callback:
                await self.callback(self, self.kwargs)