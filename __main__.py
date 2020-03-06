'''
agol-validator

Usage:
    agol-validator ORG USER [--save_report=<dir> --dry --verbose]

Arguments:
    ORG     AGOL Portal to connect to
    USER    AGOL User for authentication
            (You will be prompted for USER's password)

Options:
    -h, --help
    -r, --save_report <dir>     Directory to save report to, e.g. `c:\\temp`
    -d, --dry                   Only run the checks, don't do any fixes [default: False]
    -v, --verbose               Print status updates to the console [default: False]

Examples:
    agol-validator https://www.arcgis.com my_agol_user --save_report=c:\\temp
'''

from docopt import docopt, DocoptExit

from validate import Validator


def main():

    try:
        args = docopt(__doc__, version = '1.0')
    except DocoptExit:
        print('\n*** Invalid input ***\n')
        print(__doc__)
    else:

        org = args['ORG']
        username = args['USER']

        report_dir = args['--save_report']
        
        if args['--dry']:
            dry = True
        else:
            dry = False
        
        if args['--verbose']:
            verbose = True
        else:
            verbose = False

        org_validator = Validator(org, username, verbose)
        org_validator.check_items(report_dir)
        if not dry:
            org_validator.fix_items(report_dir)


if __name__ == '__main__':
    main()