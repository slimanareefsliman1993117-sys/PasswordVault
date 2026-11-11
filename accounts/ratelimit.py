"""Database-backed request limits, shared by every worker using the database."""
from functools import wraps
from hashlib import sha256
import time

from django.db.models import F
from django.http import HttpResponseForbidden

from .models import RateLimitBucket


def ratelimit(*, key, rate, method, block):
    count, unit = rate.split('/')
    maximum = int(count)
    period = {'m': 60, 'h': 3600}[unit]

    def decorate(view):
        @wraps(view)
        def limited(request, *args, **kwargs):
            if request.method == method:
                now = int(time.time())
                window = now // period
                identity = f'{view.__module__}.{view.__qualname__}:{request.META.get("REMOTE_ADDR", "")}:{window}'
                digest = sha256(identity.encode()).hexdigest()
                bucket, created = RateLimitBucket.objects.get_or_create(
                    key=digest, defaults={'expires_at': (window + 1) * period})
                if created:
                    RateLimitBucket.objects.filter(expires_at__lte=now).delete()
                accepted = RateLimitBucket.objects.filter(pk=bucket.pk, count__lt=maximum).update(count=F('count') + 1)
                if not accepted:
                    return HttpResponseForbidden('Too many attempts. Please wait a minute and try again.')
            return view(request, *args, **kwargs)
        return limited
    return decorate
