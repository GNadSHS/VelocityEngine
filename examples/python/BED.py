#!/usr/bin/env python
"""
Runs Biological Effective Dose (BED) calculation.

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

# requires patient 'external DR sum' already imported
PATIENT_ID = '10052012'
PRIMARY_UID = '1.2.840.113619.2.55.3.278435321.302.1313753121.582'
SECONDARY_UID = '1.2.246.352.71.7.1873493392.2486330.20110829091331'
REG_NAME = 'DICOM'
STRUCT_1 = 'Bladder'
STRUCTSET_1UID = '1.2.276.0.7230010.3.1.4.1492057408.5156.1349471628.10'
DEFAULT_ALPHABETA_TISSUE = 3


def main(args):
    """
    Execution of example source code

    Input argument args contains patient id and Velocity app type.
    If not assigned from console then values from script are used.

    """
    e = create_engine(args.app)  # creation of velocity engine instance

    orThrow(e.loadPatientByPatientId(args.patient_id), e=e)
    print('Loaded patient: {}'.format(args.patient_id))
    orThrow(e.loadPrimaryVolumeByUID(PRIMARY_UID), e=e)
    print('Loaded primary volume: {}'.format(PRIMARY_UID))
    orThrow(e.loadSecondaryVolumeByUID(SECONDARY_UID), e=e)
    print('Loaded secondary volume: {}'.format(SECONDARY_UID))

    # create registration if it doesn't exist
    # regOps = e.getRegistrationOperations()
    orThrow(e.loadRegistrationByName(REG_NAME), e=e)
    print('Loaded existing registration object: {}'.format(REG_NAME))

    structure = e.loadStructureByName(STRUCT_1, STRUCTSET_1UID)
    orThrow(structure, e=e)
    print('Loaded existing structure: {}'.format(STRUCT_1))

    bedStructure = velocity.BedStructureVariables()
    bedStructure.structureId = structure.getVelocityId()
    bedStructure.alphaBetaRatio = 2
    bedStructure.structureName = structure.getName()

    calculationData = velocity.BedDoseCalculationData()
    calculationData.bedVariablesByStructure = velocity.BedStructureVariablesList([bedStructure])
    calculationData.fractions = 25

    backgroundData = velocity.BedBackgroundData()
    backgroundData.alphaBetaRatio = DEFAULT_ALPHABETA_TISSUE

    vo = e.getVolumeOperations()
    orThrow(vo.createBEDose(calculationData, backgroundData, False) != -1, vo)
    print('Biological Effective Dose created')


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


if __name__ == "__main__":
    args = parse_arguments()
    main(args)
