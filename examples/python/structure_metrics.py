#!/usr/bin/env python
"""
Copies structures using a deformable.
Calculates minimum, median, mean, and standard deviation values,
comparing them across the deformable or with the proceeding rigid.

REQUIRES:
- created user of type Script in Velocity
- suitable patient data already imported in Velocity
- existing registration for selected volumes (doesnt need to be run - just created)
- existing structure set for primary volume with at least one structure
  (some structure types might not be possible to copy, try type e.g. External (auto))

note:
- EXCEPTION StopIteration - in case no structure set or structure was found for given name

Can be run in 2 different ways - for GRID or WORKSTATION.
This is specified using --app input argument.

"""
import velocity
import datetime
import argparse
import atexit

APP_TYPE = "grid"  # grid or workstation (can be overriden from console e.g. --app_type workstation)
DB_PATH = r"/Velocity/Databases/vscDatabase"  # will be used only if app == workstation
DB_NAME = "vscDatabase"                       # will be used only if app == grid
DB_USER = "script"
DB_PASS = "script"
DB_IP   = "127.0.0.1"
DB_PORT = 57000

# requires "sixCBCT, AdaptiveMonitoring" data already imported
PATIENT_ID = 'AW3Y6TA684'  # can be overriden from console e.g. --patient_id xyz
PRIMARY_UID = '1.3.12.2.1107.5.1.4.54841.30000011071412175920300003025'
SECONDARY_UID = '1.2.246.352.61.2.4621874044879001489.17114159699319862401'
REGISTRATION_NAME = 'CBCT MULTI'
RIGID_NAME = "RIGID"
STRUCTURE_SET_NAME = "Original SIM"
STRUCTURE_NAME = "Mandible"


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
    orThrow(e.loadRegistrationByName(REGISTRATION_NAME), e=e)
    print('Loaded registration: {}'.format(REGISTRATION_NAME))

    # rops = e.getRegistrationOperations()
    sops = e.getStructureOperations()

    primaryVol = e.getPrimaryVolume()
    # secondaryVol = e.getSecondaryVolume()

    # find an external structure, throws StopIteration if not found
    primarySet = next(s for s in primaryVol.getStructureSets() if s.getName() == STRUCTURE_SET_NAME)
    structure = next(s for s in primarySet.getStructures() if s.getName() == STRUCTURE_NAME)
    print('Using structure "{}" from structure set "{}"'.format(structure.getName(), primarySet.getName()))

    # create a new structure set on the secondary volume
    targetSetName = datetime.datetime.now().isoformat()[:16]
    targetSet = sops.createStructureSet(targetSetName, False)
    orThrow(targetSet, sops)

    # copy the external to the new structure set
    print('Copying structure to secondary...')
    newStructures = sops.copyStructuresToSecondary([structure.getVelocityId()], targetSet.getVelocityId())

    # IMPORTANT: call save after finishing a set of modifications to a structure set
    targetSet = sops.saveStructureSet(targetSet.getVelocityId())

    orThrow(len(newStructures) == 1, sops)
    newStructureId = next(iter(newStructures))
    newStructure = newStructures[newStructureId]
    print('Structure copied to secondary, computing metrics...')

    # show metrics on registration used for copying
    metrics(sops=sops, structure=structure, newStructure=newStructure)

    # now on an alternative registration
    orThrow(e.loadRegistrationByName(RIGID_NAME), e=e)
    print('Loaded registration: {}'.format(RIGID_NAME))
    metrics(sops=sops, structure=structure, newStructure=newStructure)


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


def metrics(sops, structure, newStructure):
    # compute metrics on the copied external structure
    c = sops.conformality(structure.getVelocityId(), newStructure.getVelocityId())
    print("Conformality: {}".format(c))
    if c < 0.0:
        print("Error: {}".format(sops.getErrorMessage()))

    mets = sops.surfaceDistanceMetrics(structure.getVelocityId(), newStructure.getVelocityId())
    if not mets.isValid:
        print("Error: {}".format(sops.getErrorMessage()))
    else:
        print(
            f"Metrics: Hausdorff={mets.hausdorffDistance}, min={mets.min},"
            f"median={mets.median}, mean={mets.mean}, stddev={mets.standardDeviation}"
        )


if __name__ == "__main__":
    args = parse_arguments()
    main(args)
