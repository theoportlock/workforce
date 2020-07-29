from concurrent.futures import ThreadPoolExecutor

class CachedThreadPoolExecutor(ThreadPoolExecutor):
    def __init__(self):
        super(CachedThreadPoolExecutor, self).__init__(max_workers=1)

    def submit(self, fn, *args, **extra):
        if self._work_queue.qsize() > 0:
            print('increasing pool size from %d to %d' % (self._max_workers, self._max_workers+1))
            self._max_workers +=1

        return super(CachedThreadPoolExecutor, self).submit(fn, *args, **extra)

pool = CachedThreadPoolExecutor()

def fibonacci(n):
    print(n)
    if n < 2:
        return n
    a = pool.submit(fibonacci, n - 1)
    b = pool.submit(fibonacci, n - 2)
    return a.result() + b.result()

print(fibonacci(10))
