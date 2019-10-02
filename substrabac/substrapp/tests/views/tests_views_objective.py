import os
import shutil
import logging
import zipfile
import copy

import mock
import requests

from django.urls import reverse
from django.test import override_settings
from requests.auth import HTTPBasicAuth

from rest_framework import status
from rest_framework.test import APITestCase

from substrapp.models import Objective
from substrapp.serializers import LedgerObjectiveSerializer

from substrapp.ledger_utils import LedgerError

from substrapp.views.objective import compute_dryrun as objective_compute_dryrun
from substrapp.utils import compute_hash, get_hash

from ..common import get_sample_objective, FakeTask, AuthenticatedClient
from ..assets import objective, datamanager, traintuple, model

MEDIA_ROOT = "/tmp/unittests_views/"


def zip_folder(path, destination):
    zipf = zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED)
    for root, dirs, files in os.walk(path):
        for f in files:
            abspath = os.path.join(root, f)
            archive_path = os.path.relpath(abspath, start=path)
            zipf.write(abspath, arcname=archive_path)
    zipf.close()


# APITestCase
@override_settings(MEDIA_ROOT=MEDIA_ROOT)
@override_settings(SITE_HOST='localhost')
@override_settings(LEDGER={'name': 'test-org', 'peer': 'test-peer'})
@override_settings(DEFAULT_DOMAIN='https://localhost')
@override_settings(LEDGER_SYNC_ENABLED=True)
class ObjectiveViewTests(APITestCase):
    client_class = AuthenticatedClient

    def setUp(self):
        if not os.path.exists(MEDIA_ROOT):
            os.makedirs(MEDIA_ROOT)

        self.objective_description, self.objective_description_filename, \
            self.objective_metrics, self.objective_metrics_filename = get_sample_objective()

        self.test_data_sample_keys = [
            "2d0f943aa81a9cb3fe84b162559ce6aff068ccb04e0cb284733b8f9d7e06517e",
            "533ee6e7b9d8b247e7e853b24547f57e6ef351852bac0418f13a0666173448f1"
        ]

        self.extra = {
            'HTTP_ACCEPT': 'application/json;version=0.0'
        }

        self.logger = logging.getLogger('django.request')
        self.previous_level = self.logger.getEffectiveLevel()
        self.logger.setLevel(logging.ERROR)

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

        self.logger.setLevel(self.previous_level)

    def test_objective_list_empty(self):
        url = reverse('substrapp:objective-list')
        with mock.patch('substrapp.views.objective.query_ledger') as mquery_ledger:
            mquery_ledger.return_value = []

            response = self.client.get(url, **self.extra)
            r = response.json()
            self.assertEqual(r, [[]])

    def test_objective_list_success(self):
        url = reverse('substrapp:objective-list')
        with mock.patch('substrapp.views.objective.query_ledger') as mquery_ledger:
            mquery_ledger.return_value = objective

            response = self.client.get(url, **self.extra)
            r = response.json()
            self.assertEqual(r, [objective])

    def test_objective_list_filter_fail(self):
        url = reverse('substrapp:objective-list')
        with mock.patch('substrapp.views.objective.query_ledger') as mquery_ledger:
            mquery_ledger.return_value = objective

            search_params = '?search=challenERRORge'
            response = self.client.get(url + search_params, **self.extra)
            r = response.json()

            self.assertIn('Malformed search filters', r['message'])

    def test_objective_list_filter_name(self):
        url = reverse('substrapp:objective-list')
        with mock.patch('substrapp.views.objective.query_ledger') as mquery_ledger:
            mquery_ledger.return_value = objective

            search_params = '?search=objective%253Aname%253ASkin%2520Lesion%2520Classification%2520Objective'
            response = self.client.get(url + search_params, **self.extra)
            r = response.json()

            self.assertEqual(len(r[0]), 2)

    def test_objective_list_filter_metrics(self):
        url = reverse('substrapp:objective-list')
        with mock.patch('substrapp.views.objective.query_ledger') as mquery_ledger:
            mquery_ledger.return_value = objective

            search_params = '?search=objective%253Ametrics%253Amacro-average%2520recall'
            response = self.client.get(url + search_params, **self.extra)
            r = response.json()

            self.assertEqual(len(r[0]), len(objective))

    def test_objective_list_filter_datamanager(self):
        url = reverse('substrapp:objective-list')
        with mock.patch('substrapp.views.objective.query_ledger') as mquery_ledger, \
                mock.patch('substrapp.views.filters_utils.query_ledger') as mquery_ledger2:
            mquery_ledger.return_value = objective
            mquery_ledger2.return_value = datamanager

            search_params = '?search=dataset%253Aname%253ASimplified%2520ISIC%25202018'
            response = self.client.get(url + search_params, **self.extra)
            r = response.json()

            self.assertEqual(len(r[0]), 1)

    def test_objective_list_filter_model(self):
        url = reverse('substrapp:objective-list')
        with mock.patch('substrapp.views.objective.query_ledger') as mquery_ledger, \
                mock.patch('substrapp.views.filters_utils.query_ledger') as mquery_ledger2:
            mquery_ledger.return_value = objective
            mquery_ledger2.return_value = traintuple

            pkhash = model[1]['traintuple']['outModel']['hash']
            search_params = f'?search=model%253Ahash%253A{pkhash}'
            response = self.client.get(url + search_params, **self.extra)
            r = response.json()

            self.assertEqual(len(r[0]), 1)

    def test_objective_retrieve(self):
        url = reverse('substrapp:objective-list')

        with mock.patch('substrapp.views.objective.get_object_from_ledger') as mget_object_from_ledger, \
                mock.patch('substrapp.views.objective.get_remote_asset') as get_remote_asset:
            mget_object_from_ledger.return_value = objective[0]

            with open(os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                   '../../../../fixtures/owkin/objectives/objective0/description.md'), 'rb') as f:
                content = f.read()

            get_remote_asset.return_value = content

            pkhash = compute_hash(content)
            search_params = f'{pkhash}/'

            response = self.client.get(url + search_params, **self.extra)
            r = response.json()

            self.assertEqual(r, objective[0])

    def test_objective_retrieve_fail(self):

        dir_path = os.path.dirname(os.path.realpath(__file__))
        url = reverse('substrapp:objective-list')

        # PK hash < 64 chars
        search_params = '42303efa663015e729159833a12ffb510ff/'
        response = self.client.get(url + search_params, **self.extra)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # PK hash not hexa
        search_params = 'X' * 64 + '/'
        response = self.client.get(url + search_params, **self.extra)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        with mock.patch('substrapp.views.objective.get_object_from_ledger') as mget_object_from_ledger:
            mget_object_from_ledger.side_effect = LedgerError('TEST')

            file_hash = get_hash(os.path.join(dir_path,
                                              "../../../../fixtures/owkin/objectives/objective0/description.md"))
            search_params = f'{file_hash}/'
            response = self.client.get(url + search_params, **self.extra)

            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_objective_create(self):
        url = reverse('substrapp:objective-list')

        dir_path = os.path.dirname(os.path.realpath(__file__))

        objective_path = os.path.join(dir_path, '../../../../fixtures/owkin/objectives/objective0/')

        description_path = os.path.join(objective_path, 'description.md')

        metrics_path = os.path.join(MEDIA_ROOT, 'metrics.zip')

        zip_folder(objective_path, metrics_path)

        pkhash = get_hash(description_path)

        test_data_manager_key = get_hash(os.path.join(
            dir_path, '../../../../fixtures/owkin/datamanagers/datamanager0/opener.py'))

        data = {
            'name': 'Simplified skin lesion classification',
            'description': open(description_path, 'rb'),
            'metrics_name': 'macro-average recall',
            'metrics': open(metrics_path, 'rb'),
            'permissions_public': True,
            'permissions_authorized_ids': [],
            'test_data_sample_keys': self.test_data_sample_keys,
            'test_data_manager_key': test_data_manager_key
        }

        with mock.patch.object(LedgerObjectiveSerializer, 'create') as mcreate:

            mcreate.return_value = {}

            response = self.client.post(url, data=data, format='multipart', **self.extra)

        self.assertEqual(response.data['pkhash'], pkhash)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data['description'].close()
        data['metrics'].close()

    def test_objective_create_dryrun(self):

        url = reverse('substrapp:objective-list')

        dir_path = os.path.dirname(os.path.realpath(__file__))

        objective_path = os.path.join(dir_path, '../../../../fixtures/owkin/objectives/objective0/')

        description_path = os.path.join(objective_path, 'description.md')

        metrics_path = os.path.join(MEDIA_ROOT, 'metrics.zip')

        zip_folder(objective_path, metrics_path)

        test_data_manager_key = get_hash(os.path.join(
            dir_path, '../../../../fixtures/owkin/datamanagers/datamanager0/opener.py'))

        data = {
            'name': 'Simplified skin lesion classification',
            'description': open(description_path, 'rb'),
            'metrics_name': 'macro-average recall',
            'metrics': open(metrics_path, 'rb'),
            'permissions_public': True,
            'permissions_authorized_ids': [],
            'test_data_sample_keys': self.test_data_sample_keys,
            'test_data_manager_key': test_data_manager_key,
            'dryrun': True
        }

        with mock.patch('substrapp.views.objective.compute_dryrun.apply_async') as mdryrun_task:

            mdryrun_task.return_value = FakeTask('42')
            response = self.client.post(url, data=data, format='multipart', **self.extra)

        self.assertEqual(response.data['id'], '42')
        self.assertEqual(response.data['message'],
                         'Your dry-run has been taken in account. '
                         'You can follow the task execution on https://localhost/task/42/')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        data['description'].close()
        data['metrics'].close()

    def test_objective_compute_dryrun(self):

        dir_path = os.path.dirname(os.path.realpath(__file__))

        objective_path = os.path.join(dir_path, '../../../../fixtures/owkin/objectives/objective0/')
        description_path = os.path.join(objective_path, 'description.md')
        zip_path = os.path.join(MEDIA_ROOT, 'metrics.zip')

        opener_path = os.path.join(dir_path, '../../../../fixtures/owkin/datamanagers/datamanager0/opener.py')

        zip_folder(objective_path, zip_path)

        with open(opener_path, 'rb') as f:
            opener_content = f.read()

        pkhash = get_hash(description_path)

        test_data_manager_key = compute_hash(opener_content)

        with mock.patch('substrapp.views.objective.get_object_from_ledger') as mdatamanager,\
                mock.patch('substrapp.views.objective.get_asset_content') as mget_asset_content:
            mdatamanager.return_value = {
                'opener': {
                    'storageAddress': 'test',
                    'hash': pkhash
                },
                'owner': 'external_node_id'
            }
            mget_asset_content.return_value = opener_content
            objective_compute_dryrun(zip_path, test_data_manager_key, pkhash)

    def test_objective_leaderboard_sort(self):
        url = reverse('substrapp:objective-leaderboard', args=[objective[0]['key']])
        with mock.patch('substrapp.views.objective.query_ledger') as mquery_ledger:
            mquery_ledger.return_value = {}

            self.client.get(url, data={'sort': 'desc'}, **self.extra)
            mquery_ledger.assert_called_with(
                fcn='queryObjectiveLeaderboard',
                args={
                    'objectiveKey': objective[0]['key'],
                    'ascendingOrder': False,
                })

            self.client.get(url, data={'sort': 'asc'}, **self.extra)
            mquery_ledger.assert_called_with(
                fcn='queryObjectiveLeaderboard',
                args={
                    'objectiveKey': objective[0]['key'],
                    'ascendingOrder': True,
                })

        response = self.client.get(url, data={'sort': 'foo'}, **self.extra)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_objective_url_rewrite_list(self):
        url = reverse('substrapp:objective-list')
        with mock.patch('substrapp.views.objective.query_ledger') as mquery_ledger, \
                mock.patch('substrapp.views.objective.get_remote_asset') as mget_remote_asset:

            # mock content
            mget_remote_asset.return_value = b'dummy binary content'
            ledger_objectives = copy.deepcopy(objective)
            for ledger_objective in ledger_objectives:
                for field in ('description', 'metrics'):
                    ledger_objective[field]['storageAddress'] = \
                        ledger_objective[field]['storageAddress'] \
                        .replace('http://testserver', 'http://remotetestserver')
            mquery_ledger.return_value = ledger_objectives

            # actual test
            res = self.client.get(url, **self.extra)
            res_objectives = res.data[0]
            self.assertEqual(len(res_objectives), len(objective))
            for i, res_objective in enumerate(res_objectives):
                for field in ('description', 'metrics'):
                    self.assertEqual(res_objective[field]['storageAddress'],
                                     objective[i][field]['storageAddress'])

    def test_objective_url_rewrite_retrieve(self):
        url = reverse('substrapp:objective-detail', args=[objective[0]['key']])
        with mock.patch('substrapp.views.objective.get_object_from_ledger') as mquery_ledger, \
                mock.patch('substrapp.views.objective.get_remote_asset') as mget_remote_asset:

            # mock content
            mget_remote_asset.return_value = b'dummy binary content'
            ledger_objective = copy.deepcopy(objective[0])
            for field in ('description', 'metrics'):
                ledger_objective[field]['storageAddress'] = \
                    ledger_objective[field]['storageAddress'].replace('http://testserver',
                                                                      'http://remotetestserver')
            mquery_ledger.return_value = ledger_objective

            # actual test
            res = self.client.get(url, **self.extra)
            for field in ('description', 'metrics'):
                self.assertEqual(res.data[field]['storageAddress'],
                                 objective[0][field]['storageAddress'])

    def test_objective_url_rewrite_download_local(self):
        objective_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            '../../../../fixtures/owkin/objectives/objective0')
        description_path = os.path.join(objective_path, 'description.md')
        metrics_path = os.path.join(objective_path, 'metrics.zip')

        with mock.patch('substrapp.views.utils.get_object_from_ledger') as mquery_ledger, \
                mock.patch('substrapp.views.utils.get_owner') as mget_owner, \
                mock.patch('substrapp.views.objective.ObjectivePermissionViewSet.get_object') \
                as mget_object:

            # mock content
            mquery_ledger.return_value = objective[0]
            mget_owner.return_value = objective[0]['owner']
            with open(description_path, 'rb') as f:
                description_content = f.read()
            with open(metrics_path, 'rb') as f:
                metrics_content = f.read()

            class MockDescription:
                path = description_path

            class MockMetrics:
                path = metrics_path

            mock_objective = Objective(pkhash="foo",
                                       description=MockDescription,
                                       metrics=MockMetrics)
            mget_object.return_value = mock_objective

            # test
            conf = (('description', 'description.md', description_content),
                    ('metrics', 'metrics.zip', metrics_content))
            for field, filename, content in conf:
                url = objective[0][field]['storageAddress']
                res = self.client.get(url, **self.extra)
                res_content = b''.join(list(res.streaming_content))
                self.assertEqual(res_content, content)
                self.assertEqual(res['Content-Disposition'],
                                 f'attachment; filename="{filename}"')

    def test_objective_url_rewrite_download_remote_allowed(self):
        objective_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            '../../../../fixtures/owkin/objectives/objective0')
        description_path = os.path.join(objective_path, 'description.md')
        metrics_path = os.path.join(objective_path, 'metrics.zip')
        with open(description_path, 'rb') as f:
            description_content = f.read()
        with open(metrics_path, 'rb') as f:
            metrics_content = f.read()

        with mock.patch('substrapp.views.utils.get_object_from_ledger') as mquery_ledger, \
                mock.patch('substrapp.views.utils.authenticate_outgoing_request') \
                as mauthenticate_outgoing_request, \
                mock.patch('substrapp.views.utils.get_owner') as mget_owner, \
                mock.patch('substrapp.utils.requests.get') as mrequests_get:
            # mock content
            mquery_ledger.return_value = objective[0]
            mauthenticate_outgoing_request.return_value = HTTPBasicAuth('foo', 'bar')
            mget_owner.return_value = 'not-OwkinMSP'

            requests_responses = []
            for filepath in (description_path, metrics_path):
                requests_response = requests.Response()
                requests_response.raw = open(filepath, 'rb')
                requests_response.status_code = status.HTTP_200_OK
                requests_responses.append(requests_response)
            mrequests_get.side_effect = requests_responses

            # test
            conf = (('description', 'description.md', description_content),
                    ('metrics', 'metrics.zip', metrics_content))
            for field, filename, content in conf:
                url = objective[0][field]['storageAddress']
                res = self.client.get(url, **self.extra)
                res_content = b''.join(list(res.streaming_content))
                self.assertEqual(res_content, content)
                self.assertEqual(res['Content-Disposition'],
                                 f'attachment; filename="{filename}"')

    def test_objective_url_rewrite_download_remote_denied(self):
        with mock.patch('substrapp.views.utils.get_object_from_ledger') as mquery_ledger, \
                mock.patch('substrapp.views.utils.authenticate_outgoing_request') \
                as mauthenticate_outgoing_request, \
                mock.patch('substrapp.views.utils.get_owner') as mget_owner, \
                mock.patch('substrapp.utils.requests.get') as mrequests_get:
            # mock content
            mquery_ledger.return_value = objective[0]
            mauthenticate_outgoing_request.return_value = HTTPBasicAuth('foo', 'bar')
            mget_owner.return_value = 'not-OwkinMSP'

            requests_response = requests.Response()
            requests_response.status_code = status.HTTP_401_UNAUTHORIZED
            requests_response._content = b'{"message": "nope"}'
            mrequests_get.return_value = requests_response

            # test
            for field in ('description', 'metrics'):
                url = objective[0][field]['storageAddress']
                res = self.client.get(url, **self.extra)
                self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
