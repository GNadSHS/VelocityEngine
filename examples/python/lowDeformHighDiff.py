#!/usr/bin/env python
"""
Highlights regions that differ strongly between the primary volume and the
deformed secondary volume while showing little local deformation.

The script subtracts the deformed secondary image (CTSIM) from the primary
cone-beam CT to build a 'Diff' volume, computes the Jacobian of the deformable
registration, and flags voxels that have a large intensity difference yet a
Jacobian close to 1 (little volume change). Those voxels are saved as a
structure, marking places where the registration may have failed to align the
images.

REQUIRES:
- created user of type Script in Velocity
- suitable patient data already imported in Velocity (primary and secondary
  volumes named below)
- existing deformable registration for the selected volumes

note:
- EXCEPTION StopIteration - in case a volume with the configured name was not found

Can be run in 2 different ways - for GRID or WORKSTATION.
This is specified using --app input argument.

"""
import velocity
import atexit
import datetime
import math
import argparse


APP_TYPE = "grid"  # grid or workstation (can be overriden from console e.g. --app_type workstation)
DB_PATH = r"/Velocity/Databases/vscDatabase"  # will be used only if app == workstation
DB_NAME = "vscDatabase"                       # will be used only if app == grid
DB_USER = "script"
DB_PASS = "script"
DB_IP   = "127.0.0.1"
DB_PORT = 57000


# Set desired patient to load, as well as image volume names and registration name.
# Note: The cone-beam CT is set as primary so that the registration
# does not escape the bounds of the smaller image.
PATIENT_ID = "Velocity_1"
PRIMVOL = "CBCT"
SECVOL = "CTSIM"
REG_NAME = "deform_01"

DIFF_VOLUME_NAME = "Diff"
OUTPUT_STRUCTURE_NAME = "LowDeformHighDiff"
DIFF_THRESHOLD = 700      # minimum absolute intensity difference to count as "high difference"
MAX_JACOBIAN_LOG = 0.5    # |log(Jacobian)| at or below this counts as "low deformation"


def main(args):
    """
    Execution of example source code

    Input argument args contains patient id and Velocity app type.
    If not assigned from console then values from script are used.

    """
    e = create_engine(args.app)  # creation of velocity engine instance

    # Load the patient and import operations
    patient = e.loadPatientByPatientId(args.patient_id)
    if not patient.isValid():
        print('Importing CBCT and CTSIM...')
        iops = e.getImportOperations()
        orThrow(iops.importDirectory(IMPORT_DIR, True))
        patient = e.loadPatientByPatientId(args.patient_id)
        orThrow(patient)
    print('Loaded patient: {}'.format(args.patient_id))

    # Get and load volumes
    volumes = patient.getVolumes()

    # Find the primary and secondary volumes by name and load them
    primaryVol = next(v for v in volumes if v.getName() == PRIMVOL)
    orThrow(e.loadPrimaryVolumeByUID(primaryVol.getVolumeUID()), e=e)
    print('Loaded primary volume: {}'.format(primaryVol.getVolumeUID()))
    secondaryVol = next(v for v in volumes if v.getName() == SECVOL)
    orThrow(e.loadSecondaryVolumeByUID(secondaryVol.getVolumeUID()), e=e)
    print('Loaded secondary volume: {}'.format(secondaryVol.getVolumeUID()))

    # Load the registration and assign a variable to registration operations
    orThrow(e.loadRegistrationByName(REG_NAME), e=e)
    print('Loaded registration: {}'.format(REG_NAME))
    regOps = e.getRegistrationOperations()
    #orThrow(regOps.saveRegistration(), regOps)

    '''
    Create subtract from primary resample volume utilizing createResampledVolume().
    The elementOperation of '2' corresponds to VolumeResampleSubtract operation.
    The result is a volume with name 'Diff'.
    Then, we print the size of the image.
    '''
    print('Creating createResampledVolume...')
    volOps = e.getVolumeOperations()
    SubVolID = volOps.createResampledVolume(2, DIFF_VOLUME_NAME)
    print('Resampled Volume ID: {}'.format(SubVolID))
    orThrow(e.loadPrimaryVolume(SubVolID), e=e)
    print('Load resampled volume: {}'.format(SubVolID))
    diffVolumetricData = volOps.getVolumetricData(SubVolID)
    orThrow(diffVolumetricData, volOps)
    diffVolumetricSize = diffVolumetricData.size[0] * diffVolumetricData.size[1] * diffVolumetricData.size[2]
    print('Calculate createResampledVolume size: {}'.format(diffVolumetricSize))

    '''
    Reload CBCT as primary and registration in order to calc Jacobian
    Note: Loading a new primary unseats the secondary, which is why
    we need to reload the secondary and the registration as well.
    '''
    orThrow(e.loadPrimaryVolumeByUID(primaryVol.getVolumeUID()), e=e)
    print('Loaded primary volume: {}'.format(primaryVol.getVolumeUID()))
    orThrow(e.loadSecondaryVolumeByUID(secondaryVol.getVolumeUID()), e=e)
    print('Loaded secondary volume: {}'.format(secondaryVol.getVolumeUID()))
    orThrow(e.loadRegistrationByName(REG_NAME), e=e)
    print('Loaded registration: {}'.format(REG_NAME))

    # Calculate the Jacobian determinants, which helps us determine the extent of
    # volume changes in each voxel.
    print('Computing Jacobian...')
    jacobian = regOps.computeJacobian()
    orThrow(jacobian, regOps)
    jacobianSize = jacobian.size[0] * jacobian.size[1] * jacobian.size[2]
    print('Calculated Jacobian size: {}'.format(jacobianSize))
    print('Done')

    '''
    Create mask from volumetric data in order to determine if there are regions
    of high difference between the primary volume and deformed secondary volume,
    but if there also was a lack of deformation in those regions.
    '''
    vops = e.getVolumeOperations()
    primaryVol = e.getPrimaryVolume()
    volumetricData = vops.getVolumetricData(primaryVol.getVelocityId())
    orThrow(volumetricData, vops)
    print('Creating mask using Diff and Jacobian...')
    diffMask = velocity.StructureMask(diffVolumetricData.size)
    voxelCount = diffVolumetricData.size[0] * diffVolumetricData.size[1] * diffVolumetricData.size[2]
    for i in range(0, voxelCount):
        isDiff = abs(diffVolumetricData.data[i]) >= DIFF_THRESHOLD
        isRigid = abs(math.log(abs(jacobian.data[i]))) <= MAX_JACOBIAN_LOG
        # Create a mask in which there is a significant difference between primary
        # and deformed secondary volume but not a significant change in volume
        diffMask.data[i] = isDiff and isRigid
    print('Done')

    # Mask should be voxel-aligned with the primary volume
    mask = velocity.StructureMask(volumetricData.size)

    # Create a new structure set on the primary volume
    sops = e.getStructureOperations()
    setName = datetime.datetime.now().isoformat()[5:16]
    set = sops.createStructureSet(setName)
    orThrow(set, sops)

    print('Creating structure from mask...')
    s1 = sops.createStructureFromMask(set.getVelocityId(), diffMask, OUTPUT_STRUCTURE_NAME)
    orThrow(s1, sops)

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

