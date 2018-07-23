# Create your tasks here
from __future__ import absolute_import, unicode_literals
from celery import shared_task
from rest_framework import status

from substrapp.conf import conf
from substrapp.models import Challenge
from substrapp.utils import invokeLedger


@shared_task
def createLedgerChallenge(args, pkhash):
    # TODO put in settings
    org = conf['orgs']['chu-nantes']
    peer = org['peers'][0]

    options = {
        'org': org,
        'peer': peer,
        'args': '{"Args":["registerChallenge", ' + args + ']}'
    }
    data, st = invokeLedger(options)

    #  if not created on ledger, delete from local db, else pass to validated true
    try:
        instance = Challenge.objects.get(pk=pkhash)
    except:
        pass
    else:
        if st != status.HTTP_201_CREATED:
            instance.delete()
        else:
            instance.validated = True
            instance.save()

    return data, st
