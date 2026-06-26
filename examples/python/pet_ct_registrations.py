#!/usr/bin/env python
"""
Tests running a manual registration, rigid registration, and performing
a deformable registration using customized settings.

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

# requires "PETCT, Deformable" data already imported
PATIENT_ID = "H&N 1"
PRIMARY_UID = '1.3.12.2.1107.5.1.4.1031.30000009080711125237500008699'
SECONDARY_UID = '1.2.840.113704.1.111.3200.1253806429.28'
REG_NAME = 'python_registration'


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

    # create registration
    regOps = e.getRegistrationOperations()
    print('Creating registration object: {}'.format(REG_NAME))
    registration = regOps.createNewRegistration(REG_NAME)
    orThrow(registration, regOps)
    orThrow(e.loadRegistration(registration.getVelocityId()), e=e)

    # first move the head into the right general area
    print('Running manual registration...')
    manualSettings = velocity.ManualRegistrationSettingsStructure()
    manualSettings.registrationMatrix = (
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        -4.9760, -273.4696, -390.25003, 1.0)
    orThrow(regOps.performManualAlignmentDICOM(manualSettings), regOps)
    print('done.')

    # now run rigid registration
    print('Running rigid registration...')
    regSettings = velocity.RigidRegistrationSettingsStructure()
    regSettings.roiStart[0] = -102.021
    regSettings.roiStart[1] = -74.7234
    regSettings.roiStart[2] = -5.49291
    regSettings.roiEnd[0] = 100.532
    regSettings.roiEnd[1] = -410.341
    regSettings.roiEnd[2] = -309.819

    regSettings.primaryStartLevel = -114.98
    regSettings.primaryEndLevel = 185.02
    regSettings.secondaryStartLevel = -115.0
    regSettings.secondaryEndLevel = 185.02

    regSettings.preProcessingMethod = 0
    regSettings.performInitialAutoAlignment = True
    regSettings.disableRotations = False
    regSettings.maximumNumberOfIterations = 45
    regSettings.minimumStepLength = 0.0001
    regSettings.maximumStepLength = 17.0
    regSettings.samplesDenominator = 10
    regSettings.numberOfHistogramBins = 25
    orThrow(regOps.performRigidRegistrationDICOM(regSettings), regOps)
    print('done.')

    print('Performing deformable registration...')
    bsplineSettings = velocity.BSplineDeformableRegistrationSettingsStructure()
    bsplineSettings.roiStart[0] = -102.021
    bsplineSettings.roiStart[1] = -74.7234
    bsplineSettings.roiStart[2] = -5.49291
    bsplineSettings.roiEnd[0] = 100.532
    bsplineSettings.roiEnd[1] = -410.341
    bsplineSettings.roiEnd[2] = -309.819

    bsplineSettings.primaryStartLevel = -114.98
    bsplineSettings.primaryEndLevel = 185.02
    bsplineSettings.secondaryStartLevel = -115.0
    bsplineSettings.secondaryEndLevel = 185.02

    bsplineSettings.preprocessingMethod = 0
    bsplineSettings.numberOfMultiResolutionLevels = 5 # so each vector setting should be length 5
    bsplineSettings.applyBoundaryContinuityConstraints = velocity.BoolList([False]*5)
    bsplineSettings.applyTopologicalRegularizer = velocity.BoolList([False]*5)
    r3dZeroes = velocity.VectorR3d(0.0)
    bsplineSettings.topologicalRegularizerDistanceLimitingCoefficient = velocity.VectorR3dList([r3dZeroes]*5)
    bsplineSettings.numberOfHistogramBins = velocity.IntList([50]*5)
    bsplineSettings.maximumNumberOfIterations = velocity.IntList([70]*5)
    bsplineSettings.maximumNumberOfConsecutiveOptimizerAttempts = velocity.IntList([10]*5)
    bsplineSettings.metricValuePercentageDifference = velocity.DoubleList([0.0]*5)
    bsplineSettings.minimumStepLength = velocity.DoubleList([0.000001]*5)
    bsplineSettings.maximumStepLength = velocity.DoubleList([100.0]*5)
    bsplineSettings.samplesDenominator = velocity.IntList([5]*5)
    bsplineSettings.relaxationFactor = velocity.DoubleList([0.9]*5)
    bsplineSettings.gradientMagnitudeTolerance = velocity.DoubleList([0.000000000000000000005]*5)
    bsplineSettings.gridCellSize = velocity.VectorR3dList(( velocity.VectorR3d(8.0), velocity.VectorR3d(10.0), velocity.VectorR3d(13.0), velocity.VectorR3d(15.0), velocity.VectorR3d(18.0) ))
    bsplineSettings.gridCellSizeType = velocity.CharList([ord('n')]*5)

    orThrow(regOps.performBsplineRegistrationDICOM(bsplineSettings), regOps)
    print('done')

    # changes are just in memory, save changes to the database
    orThrow(regOps.saveRegistration(), regOps)


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
