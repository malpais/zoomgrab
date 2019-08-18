#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import csv
import json
import click
from gophish import Gophish
from gophish.models import User, Group


"""
OutputHandler - Consolidating any output-related functionality under a single class

If the user wants to save search results to disk, zoomgrab will perform some checks
and act appropriately if directories are missing. Depending on the user's preferred
`output_format`, the OutputHandler object will write the results using that format.
"""
class OutputHandler():
    target_domain = ''
    directory = None
    output_format = None
    output_path = ''
    username_format = 'full'
    results = []
    all_results = []
    csv_field_names = ['Email', 'Full Name', 'Title', 'Location']
    gophish_api = None

    def __init__(self, directory, target_domain, username_format, output_format, gophish_url, gophish_api_key):
        self.directory = directory
        self.target_domain = target_domain
        self.username_format = username_format
        self.output_format = output_format
        self.gophish_api = Gophish(gophish_api_key, host=gophish_url, verify=False) if (gophish_url and gophish_api_key) else None

        if self.directory and self.output_format:
            # If the output directory doesn't exist then create it
            if not os.path.exists(self.directory):
                os.mkdir(self.directory)

            self.output_path = f'{self.directory}/{self.target_domain}-{self.username_format}'

            # if the user wants to store results as a csv, write the csv header first
            if self.output_format == 'csv':
                self._write_csv_header()


    """
    Saves results to the user-specified output format

    param results: list of employee profile data to be saved
    """
    def _save_results(self, results):
        self.results = results
        self.all_results += results
        if self.directory and self.output_format:
            if self.output_format == 'flat':
                self._write_flat()
            elif self.output_format == 'csv':
                self._write_csv()
            elif self.output_format == 'json':
                self._write_json()


    """
    Print all results to stdout
    """
    def _print_results(self):
        for person in self.all_results:
            click.echo(f'[*] {person["Email"]}|{person["Full Name"]}|{person["Title"]}|{person["Location"]}')


    """
    Write results to a flat text file
    """
    def _write_flat(self):
        with open(f'{self.output_path}.txt', 'a') as fh:
            for person in self.results:
                fh.write(f'{person["Email"]}|{person["Full Name"]}|{person["Title"]}|{person["Location"]}\n')


    """
    Write csv header to disk
    """
    def _write_csv_header(self):
        with open(f'{self.output_path}.csv', 'w') as fh:
            csv_writer = csv.DictWriter(fh, fieldnames=self.csv_field_names, delimiter=',', quoting=csv.QUOTE_MINIMAL)
            csv_writer.writeheader()


    """
    Write results to a csv
    """
    def _write_csv(self):
        with open(f'{self.output_path}.csv', 'a') as fh:
            csv_writer = csv.DictWriter(fh, fieldnames=self.csv_field_names, delimiter=',', quoting=csv.QUOTE_MINIMAL)
            for person in self.results:
                csv_writer.writerow(person)


    """
    Write results as json objects to a file
    """
    def _write_json(self):
        with open(f'{self.output_path}.json', 'a') as fh:
            for person in self.results:
                fh.write(f'{json.dumps(person)}\n')

    """
    Take ZoomInfo results and import into a GoPhish instance via API calls.
    """
    def _import_into_gophish(self):
        users = self._zoom_results_to_gophish_users()
        group_name = f'{self.target_domain.split(".")[0]}-all'

        # Get user groups from gophish and match against current domain
        found_group_id = [group.id for group in self.gophish_api.groups.get() if group.name == group_name]

        if found_group_id:
            # Takes current results and PUTs them into the existing group in gophish
            click.secho(f'[+] gophish > updating existing users group \'{group_name}\'', fg='green')
            group_id = found_group_id[0]
            group = self.gophish_api.groups.get(group_id)
            group.targets = users
            group = self.gophish_api.groups.put(group)
        else:
            # Adds ZoomInfo results into gophish user group for domain
            click.secho(f'[+] gophish > adding users to group \'{group_name}\'', fg='green')
            group = self.gophish_api.groups.post(Group(name=group_name, targets=users))

    """
    Convert ZoomInfo results into GoPhish user objects.

    return list: All GoPhish user objects.
    """
    def _zoom_results_to_gophish_users(self):
        user_objects = []
        for result in self.all_results:
            full_name = result['Full Name'].split(' ')
            first_name, last_name = full_name[0], full_name[-1]
            user_objects.append(User(
                first_name=first_name,
                last_name=last_name,
                email=result['Email'],
                position=result['Title'],
            ))
        return user_objects
