#!/usr/bin/env python
"""
Tests import operations DICOM file import.

REQUIRES:
- created user of type Script in Velocity
- suitable patient data already imported in Velocity

Can be run in 2 different ways - for GRID or WORKSTATION.
This is specified using --app input argument.

"""
import velocity
import argparse
import atexit

APP_TYPE = "grid"  # grid or workstation (can be overriden from console e.g. --app_type workstation)
DB_PATH = r"/Velocity/Databases/vscDatabase"  # will be used only if app == workstation
DB_NAME = "vscDatabase"                       # will be used only if app == grid
DB_USER = "script"
DB_PASS = "script"
DB_IP   = "127.0.0.1"
DB_PORT = 57000

PATIENT_ID = '0045'
IMPORT_DIR = '/demodata/SPECT, Liver'


def main(args):
    """
    Execution of example source code

    Input argument args contains patient id and Velocity app type.
    If not assigned from console then values from script are used.

    """
    e = create_engine(args.app)  # creation of velocity engine instance

    # try to list liver patient volumes
    loadAndListVolumes(args.patient_id, e=e)

    # import the liver patient
    iops = e.getImportOperations()

    print('Importing SPECT, Liver ...')
    if iops.importDirectory(IMPORT_DIR, True):
        print('Successfully imported.')
    else:
        print('Import error: {}'.format(iops.getErrorMessage()))

    # try again to list the volumes for the liver patient
    loadAndListVolumes(args.patient_id, e=e)


def parse_arguments():
    """
    This method enables usege of console input arguments for PATIENT_ID and APP_TYPE.

    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--app",
        type=str.lower,
        choices=["grid", "workstation"],
        default=APP_TYPE,
        help="Application type [grid/workstation]"
    )
    parser.add_argument(
        "--patient_id",
        type=str,
        default=PATIENT_ID,
        help="Database user. User needs to be created in Velocity before running script. User type has to be Script."
    )
    args = parser.parse_args()
    print(f"Starting example with APP TYPE = {args.app} and PATIENT ID = {args.patient_id}")
    return args


def orThrow(c, e):
    if not c or (hasattr(c, 'isValid') and not c.isValid()):
        raise RuntimeError(e.getErrorMessage())


def create_engine(app_type):
    """
    Creates the Velocity engine client and login. After that we can load
    patients and volumes using engine as if it was a client.

    """
    e = velocity.VelocityEngine()
    if app_type.lower() == "workstation":
        orThrow(e.loginToWorkstation(DB_USER, DB_PASS, DB_PATH, True), e)
    elif app_type.lower() == "grid":
        orThrow(e.loginToGrid(DB_USER, DB_PASS, DB_IP, DB_PORT, DB_NAME), e)
    else:
        raise ValueError(f"Unknown application type {app_type}. Choose either grid/workstation")
    atexit.register(e.logout)  # ensure we log out when the script ends
    return e


def loadAndListVolumes(patientId, e):
    """
    Function to load a patient and list the volume uids.

    """
    patient = e.loadPatientByPatientId(patientId)
    if not patient.isValid():
        print('Could not load patient id {}, error: {}'.format(patientId, e.getErrorMessage()))
    else:
        volIds = e.getPatientVolumeUIDs(patientId)
        print('Patient id {} has volume UIDs: {}'.format(patientId, volIds))


if __name__ == "__main__":
    args = parse_arguments()
    main(args)
