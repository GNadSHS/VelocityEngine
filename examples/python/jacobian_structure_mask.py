#!/usr/bin/env python
"""
SCRIPT DOES:
- Creates a deformable registration using default settings.
- Uses the Jacobian and other volumetric information to create a
  structure mask that identifies rigid areas like bone that have been
  deformed under the registration.
- Converts a structure mask into a structure.
- Applies post processing operations like margin to create a new structure.
- Creates a structure set with two structures described above.

REQUIRES:
- created user of type Script in Velocity
- suitable patient data already imported in Velocity

Can be run in 2 different ways - for GRID or WORKSTATION.
This is specified using --app input argument.

"""
import velocity
import math
import argparse
import atexit
import datetime

APP_TYPE = "grid"  # grid or workstation (can be overriden from console e.g. --app_type workstation)
DB_PATH = r"/Velocity/Databases/vscDatabase"  # will be used only if app == workstation
DB_NAME = "vscDatabase"                       # will be used only if app == grid
DB_USER = "script"
DB_PASS = "script"
DB_IP   = "127.0.0.1"
DB_PORT = 57000

# requires "OPT 3, CBCT adaptive" data
IMPORT_DIR = r"C:\demodata\OPT 3, CBCT adaptive"
PATIENT_ID = "H&N 3"
PRIMVOL = "CTSIM"
SECVOL = "CBCT"
REG_NAME = "python_registration"


def main(args):
    """
    Execution of example source code

    Input argument args contains patient id and Velocity app type.
    If not assigned from console then values from script are used.

    """
    e = create_engine(args.app)  # creation of velocity engine instance

    patient = e.loadPatientByPatientId(args.patient_id)
    if not patient.isValid():
        print('Importing CBCT and CTSIM...')
        iops = e.getImportOperations()
        orThrow(iops.importDirectory(IMPORT_DIR, True), e=e)
        patient = e.loadPatientByPatientId(args.patient_id)
        orThrow(patient, e=e)
    print('Loaded patient: {}'.format(args.patient_id))

    # get and load volumes
    volumes = patient.getVolumes()

    primaryVol = next(v for v in volumes if v.getName() == PRIMVOL)
    secondaryVol = next(v for v in volumes if v.getName() == SECVOL)

    orThrow(e.loadPrimaryVolumeByUID(primaryVol.getVolumeUID()), e=e)
    print('Loaded primary volume: {}'.format(primaryVol.getVolumeUID()))
    orThrow(e.loadSecondaryVolumeByUID(secondaryVol.getVolumeUID()), e=e)
    print('Loaded secondary volume: {}'.format(secondaryVol.getVolumeUID()))

    # create registration
    regOps = e.getRegistrationOperations()
    print('Creating registration object: {}'.format(REG_NAME))
    registration = regOps.createNewRegistration(REG_NAME)
    orThrow(registration, regOps)
    orThrow(e.loadRegistration(registration.getVelocityId()), e=e)

    # now run rigid registration
    print('Running rigid registration...')
    regSettings = velocity.RigidRegistrationSettingsStructure()
    orThrow(regOps.performRigidRegistrationDICOM(regSettings), regOps)
    print('done.')

    print('Performing deformable registration...')
    bsplineSettings = velocity.BSplineDeformableRegistrationSettingsStructure()
    orThrow(regOps.performBsplineRegistrationDICOM(bsplineSettings), regOps)
    print('done')

    # changes are just in memory, save changes to the database
    orThrow(regOps.saveRegistration(), regOps)

    print('Computing Jacobian...')
    jacobian = regOps.computeJacobian()
    orThrow(jacobian, regOps)
    print('done')

    # create mask from volumetric data
    thresholdValue = 800  # HU
    vops = e.getVolumeOperations()
    primaryVol = e.getPrimaryVolume()
    volumetricData = vops.getVolumetricData(primaryVol.getVelocityId())
    orThrow(volumetricData, vops)

    # mask should be voxel-aligned with the volume
    mask = velocity.StructureMask(volumetricData.size)

    print('Creating mask from threshold... ')
    for i in range(0, volumetricData.size[0]*volumetricData.size[1]*volumetricData.size[2]):
        isDense = volumetricData.data[i] >= thresholdValue
        isNonRigid = abs(math.log(abs(jacobian.data[i]))) >= 0.5
        # find dense material like bone that had non-rigid deformation
        mask.data[i] = isDense and isNonRigid
    print('done')

    # create a new structure set on the primary volume
    sops = e.getStructureOperations()
    setName = datetime.datetime.now().isoformat()[:16]
    set = sops.createStructureSet(setName)
    orThrow(set, sops)

    print('Creating structure from mask ... ')
    s1 = sops.createStructureFromMask(set.getVelocityId(), mask, "mask_API")
    orThrow(s1, sops)

    # create a new structure by applying a margin
    s2 = sops.createStructure(set.getVelocityId(), "mask_API + Margin")
    orThrow(s2, sops)

    marginSettings = velocity.MarginSettings(5)

    print('Applying margin ... ')
    s2 = sops.margin(set.getVelocityId(), s1.getVelocityId(), s2.getVelocityId(), marginSettings)
    orThrow(s2, sops)

    # IMPORTANT: call save after finishing a set of modifications to the structure set
    sops.saveStructureSet(set.getVelocityId())

    print('Done.')


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
