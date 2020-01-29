'''
validate.py

Usage:
    validate.py validate --org=<org> --user=<user> [--save_report=<report_path>]

Arguments:
    org           AGOL Portal to connect to [defualt: https://www.arcgis.com]
    user          AGOL User for authentication
    report_path   Folder to save report to, eg `c:\\temp`

Examples:
    validate.py validate --org=https://www.arcgis.com --user=me --save_report=c:\\temp
'''

import arcgis
import arcpy
import csv
import datetime
import getpass
import json
# import logging

import pandas as pd

from docopt import docopt

import checks


class validator:

    #: A list of log entries, format TBD
    report = []

    #: A list of feature service item objects generated by trawling all of 
    #: the user's folders
    feature_service_items = []

    #: A dictionary of items and their folder
    itemid_and_folder = {}

    #: A dictionary of the metatable records, indexed by the metatable's itemid
    #: values: {item_id: [table_sgid_name, table_agol_name]}
    metatable_dict = {}

    #: Tags or words that should be uppercased, saved as lower to check against
    uppercased_tags = ['2g', '3g', '4g', 'agrc', 'aog', 'at&t', 'blm', 'brat', 'caf', 'cdl', 'daq', 'dfcm', 'dfirm', 'dwq', 'e911', 'ems', 'fae', 'fcc', 'fema', 'gcdb', 'gis', 'gnis', 'hava', 'huc', 'lir', 'lrs', 'lte', 'luca', 'mrrc', 'nca', 'ng911', 'nox', 'npsbn', 'ntia', 'nwi', 'plss', 'pm10', 'psap', 'sbdc', 'sbi', 'sgid', 'sitla', 'sligp', 'trax', 'uca', 'udot', 'ugs', 'uhp', 'uic', 'us', 'usdw', 'usfs', 'usfws', 'usps', 'ustc', 'ut', 'uta', 'vcp', 'vista', 'voc']

    #: Articles that should be left lowercase.
    articles = ['a', 'the', 'of', 'is', 'in']

    #: Tags that should be deleted
    tags_to_delete = ['.sd', 'service definition']

    def __init__(self, portal, user, metatable):
        self.username = user
        self.gis = arcgis.gis.GIS(portal, user, getpass.getpass(f'{user}\'s password for {portal}:'))

        user_item = self.gis.users.me

        #: Build list of folders. 'None' gives us the root folder.
        print(f'Getting {user}\'s folders...')
        folders = [None]
        for folder in user_item.folders:
            folders.append(folder['title'])

        #: Get info for every item in every folder
        print('Getting item objects...')
        for folder in folders:
            for item in user_item.items(folder, 1000):
                if item.type == 'Feature Service':
                    self.feature_service_items.append(item)
                    self.itemid_and_folder[item.itemid] = folder

        #: Read the metatable into memory as a dictionary based on itemid.
        #: Getting this once so we don't have to re-read every iteration
        print('Getting metatable info')
        with arcpy.da.SearchCursor(metatable, ['TABLENAME', 'AGOL_ITEM_ID', 'AGOL_PUBLISHED_NAME']) as table_cursor:
            for row in table_cursor:
                table_sgid_name, table_agol_itemid, table_agol_name = row
                self.metatable_dict[table_agol_itemid] = [table_sgid_name, table_agol_name]


    def check_items(self, report_path):
        '''
        For each hosted feature layer, check:
            > Tags for malformed spacing, standard AGRC/SGID tags
                item.update({'tags':[tags]})
            > Group & Folder (?) to match source data category
                gis.content.share(item, everyone=True, groups=<Open Data Group>)
                item.move(folder)
            > Delete Protection enabled
                item.protect=True
            > Downloads enabled
                manager = arcgis.features.FeatureLayerCollection.fromitem(item).manager
                manager.update_definition({ 'capabilities': 'Query,Extract' })
            > Title against metatable
                item.update({'title':title})
            > Metadata against SGID (Waiting until 2.5's arcpy metadata tools?)

        Also, check the following:
            > Duplicate tags
        '''

        #: Create a dataframe to hold our report info
        itemids = [item.itemid for item in self.feature_service_items]
        columns = ['fix_title', 'old_title', 'new_title',
                   'fix_groups', 'old_groups', 'new_group',
                   'fix_folder', 'old_folder', 'new_folder',
                   'fix_tags', 'old_tags', 'new_tags',
                   'fix_downloads',
                   'fix_delete_protection']
        report = pd.DataFrame(index=itemids, columns=columns)

        for item in self.feature_service_items:

            print(f'Checking {item.title}...')
            
            #: run the checks, return the correct values
            #: once we've got all the properties to be changed, build the report

            #: Get the list of the correct tags
            tags = checks.check_tags(item, self.tags_to_delete, self.uppercased_tags, self.articles)

            #: Get the correct name, group, and folder strings
            title, group, folder = checks.get_category_and_name(item, self.metatable_dict)
        
            #: Now .update() tags and title if needed (be greedy; update both if
            #: only one is needed to save time calling .update() twice
            # if sorted(tags) != sorted(item.tags) or title != item.title:
            #     item.update({'tags':tags, 'title':title})

            itemid = item.itemid

            
            if title != 'Not SGID':
                
                #: Title check
                if title != item.title:
                    title_data = ['Y', item.title, title]
                else:
                    title_data = ['N', item.title, '']  #: Include the old title for readability
                title_cols = ['fix_title', 'old_title', 'new_title']
                report.loc[itemid, title_cols] = title_data

                #: Groups check
                try:
                    current_groups = [group.title for group in item.shared_with['groups']]
                except:
                    current_groups = ['Error']
                if current_groups == 'Error':
                    groups_data = ['N', 'Can\'t get group', '']
                elif group not in current_groups:
                    groups_data = ['Y', '; '.join(current_groups), group]
                else:
                    groups_data = ['N', '', '']
                groups_cols = ['fix_tags', 'old_groups', 'new_group']
                report.loc[itemid, groups_cols] = groups_data
            
                #: Folder check
                current_folder = self.itemid_and_folder[itemid]
                if folder != current_folder:
                    folder_data = ['Y', current_folder, folder]
                else:
                    folder_data = ['N', '', '']
                folder_cols = ['fix_folder', 'old_folder', 'new_folder']
                report.loc[itemid, folder_cols] = folder_data

            #: Tags check
            if sorted(tags) != sorted(item.tags):
                tags_data = ['Y', '; '.join(item.tags), '; '.join(tags)]
            else:
                tags_data = ['N', '', '']
            tags_cols = ['fix_tags', 'old_tags', 'new_tags']
            report.loc[itemid, tags_cols] = tags_data

            #: Downloads check
            try:
                manager = arcgis.features.FeatureLayerCollection.fromitem(item).manager
                properties = json.loads(str(manager.properties))
            except:
                properties = None
            if properties and 'Extract' not in properties['capabilities']:
                protect_data = ['Y']
            else:
                protect_data = ['N']
            protect_cols = ['fix_downloads']
            report.loc[itemid, protect_cols] = protect_data

            #: Delete Protection check
            if not item.protected:
                protect_data = ['Y']
            else:
                protect_data = ['N']
            protect_cols = ['fix_delete_protection']
            report.loc[itemid, protect_cols] = protect_data

        report.to_csv(report_path)

        return(report)


    def fix_items(self, report):


        report_dict = report.to_dict('index')

        for itemid in report_dict:
            item = self.feature_service_items[itemid]
            
            #: Tags and title combined .update()
            update_dict = {}
            if report_dict[itemid]['fix_title'] == 'Y':
                new_title = report_dict[itemid]['new_title']
                update_dict['title'] = new_title
            if report_dict[itemid]['fix_tags'] == 'Y':
                new_tags = report_dict[itemid]['new_tags']
                update_dict['tags'] = new_tags.split('; ')
            if update_dict:
                item.update(update_dict)

            #: Group
            if report_dict[itemid]['fix_groups'] == 'Y':
                new_group = report_dict[itemid]['new_group']
                item.share(everyone=True, groups=[new_group])

            #: Folder
            if report_dict[itemid]['fix_folder'] == 'Y':
                new_folder = report_dict[itemid]['new_folder']
                item.move(new_folder)

            #: Delete Protection
            if report_dict[itemid]['fix_delete_protection'] == 'Y':
                item.protect = True

            #: Enable Downloads
            if report_dict[itemid]['fix_downloads'] == 'Y':
                manager = arcgis.features.FeatureLayerCollection.fromitem(item).manager
                manager.update_definition({ 'capabilities': 'Query,Extract' })

if __name__ == '__main__':
    agrc = validator('https://www.arcgis.com', 'UtahAGRC', r'C:\gis\Projects\Data\internal.agrc.utah.gov.sde\SGID.META.AGOLItems')

    agrc.check_items(r'c:\temp\validator1.csv')