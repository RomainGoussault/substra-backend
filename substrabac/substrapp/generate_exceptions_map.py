import os
import inspect
import json


EXCEPTION_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exceptions.json')

# Modules to inspect
os.environ['DJANGO_SETTINGS_MODULE'] = 'substrabac.settings.dev'
import docker.errors, requests.exceptions, celery.exceptions, tarfile, \
    django.core.exceptions, django.urls, django.db, django.http, django.db.transaction,\
    rest_framework.exceptions

MODULES = [docker.errors, requests.exceptions, celery.exceptions, tarfile,
           django.core.exceptions, django.urls, django.db, django.http, django.db.transaction,
           rest_framework.exceptions]


def exception_tree(cls, exceptions_classes):
    exceptions_classes.add(cls.__name__)
    for subcls in cls.__subclasses__():
        exception_tree(subcls, exceptions_classes)


def find_exception(module):
    exceptions_classes = [ename for ename, eclass in inspect.getmembers(module, inspect.isclass)
                          if issubclass(eclass, BaseException)]

    for submodule in inspect.getmembers(module, inspect.ismodule):
        exceptions_classes += [ename for ename, eclass in inspect.getmembers(module, inspect.isclass)
                               if issubclass(eclass, BaseException)]
    return exceptions_classes

if __name__ == '__main__':

    exceptions_classes = set()
    for errors_module in MODULES:
        exceptions_classes.update(find_exception(errors_module))
    exception_tree(BaseException, exceptions_classes)

    if os.path.exists(EXCEPTION_PATH):
        # Append values to it
        json_exceptions = json.load(open(EXCEPTION_PATH))

        exceptions_classes = exceptions_classes.difference(set(json_exceptions.keys()))
        start_value = max(map(int, json_exceptions.values()))

        for code_exception, exception_name in enumerate(exceptions_classes, start=start_value + 1):
            json_exceptions[exception_name] = '%04d' % code_exception

        with open(EXCEPTION_PATH, 'w') as outfile:
            json.dump(json_exceptions, outfile, indent=4)

    else:
        # Generate the json exceptions
        json_exceptions = dict()
        for code_exception, exception_name in enumerate(exceptions_classes, start=1):
            json_exceptions[exception_name] = '%04d' % code_exception

        with open(EXCEPTION_PATH, 'w') as outfile:
            json.dump(json_exceptions, outfile, indent=4)
