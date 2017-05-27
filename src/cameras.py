import yaml
import numpy as np
import os
import matplotlib.pyplot as pyplt
from RayGeometry import *


class Camera:
	def __init__(self):
		self.camera_name = None
		self.camera_overlaps = None
		self.intrinsics = np.zeros((3, 3), dtype='float32')
		self.extrinsics_relative = np.zeros((4,4), dtype='float32')
		# Current calibration file does not have absolute parameters
		# self.extrinsics_absolute = np.zeros((4,4), dtype='float32')
		self.distortion = np.zeros((4, 1), dtype='float32')
		self.resolution = np.zeros((2, 1), dtype='int32')
		self.fx = 0
		self.fy = 0
		self.fov_x = 0
		self.favg = 0
		self.cam_collection = None
		self.init_complete = False
		self.cop_col_left = 0
		self.cop_col_right = 0
		self.cop_rtheta_left = 0
		self.cop_rtheta_right = 0
		self.odsleft_xnorm = 0
		self.odsright_xnorm = 0

	def loadCameraFromYaml(self, yaml_calibration, cam_name):
		self.camera_name = cam_name
		self.resolution[0] = yaml_calibration[cam_name]['resolution'][0]
		self.resolution[1] = yaml_calibration[cam_name]['resolution'][1]
		
		intrinsics_vector = yaml_calibration[cam_name]['intrinsics']
		self.intrinsics[0][0] = intrinsics_vector[0]
		self.fx = intrinsics_vector[0]
		self.fov_x = 2*np.arctan2(self.resolution[0], self.fx)
		self.intrinsics[1][1] = intrinsics_vector[1]
		self.fy = intrinsics_vector[1]
		self.intrinsics[0][2] = intrinsics_vector[2]/self.resolution[0]
		self.intrinsics[1][2] = intrinsics_vector[3]/self.resolution[1]
		self.intrinsics[2][2] = 1
		self.favg = (self.fx + self.fy)/2
		self.intrinsics_inverse = np.linalg.inv(self.intrinsics)

		self.camera_overlaps = yaml_calibration[cam_name]['cam_overlaps']
		try:
			self.extrinsics_relative = yaml_calibration[cam_name]['T_cn_cnm1']
		except Exception as e:
			#shift=[[0, 0, 0, 1], [0, 0, 0, 0], [0, 0, 0, 1],[0, 0, 0, 0]]
			self.extrinsics_relative = np.identity(4, dtype='float32')
		self.distortion = yaml_calibration[cam_name]['distortion_coeffs']

		self.init_complete = True


	def getIntrinsics(self):
		self.cameraSanityCheck()
		return self.intrinsics

	def getExtrinsics(self):
		self.cameraSanityCheck()
		return self.extrinsics_relative

	def cameraSanityCheck(self):
		if self.init_complete is False:
			raise RuntimeError('Camera not initialized. Initialize camera before using it.')

	def getRayForPixel(self, x, y):
		self.cameraSanityCheck()
		pix_homo = np.asarray([x, y, 1], dtype='float32')
		ray = np.dot(self.intrinsics_inverse, pix_homo)
		return ray

	def transformRayToCameraRef(self, ray, camera_extrinsics):
		self.cameraSanityCheck()
		ray_homogeneous = np.append(ray, 1)
		ray=np.dot(camera_extrinsics, ray_homogeneous)
		#normalize ray again
		return ray[0:3]/ray[3]

	def getFieldOfView(self):
		return self.fov_x

	def getFieldOfViewInDegrees(self):
		return radians2Degrees(self.fov_x)

	def getIncidentColumn(self, theta, offsetByWidth=True):
		if theta > (self.fov_x/2):
			raise Warning('Theta is larger than the field of view. ')
		
		norm = np.tan(np.abs(theta))
		if offsetByWidth:
			norm = norm + 0.5
		else:
			norm = 0.5-norm
		# Do not let values go beyond 0 and 1
		np.clip(norm, 0.0, 1.0)
		return unnormalizeX(norm, self.resolution[0])

	def setCOPLeft(self, cop_left):
		self.cop_col_left = cop_left

	def setCOPRight(self, cop_right):
		self.cop_col_right = cop_right

	def getCOPLeft(self):
		return self.cop_col_left

	def getCOPRight(self):
		return self.cop_col_right

	def setCOPRelativeAngleLeft(self, theta):
		self.cop_rtheta_left = theta
		self.cop_col_left = self.getIncidentColumn(theta, offsetByWidth=True)

	def setCOPRelativeAngleRight(self, theta):
		self.cop_rtheta_right = theta
		self.cop_col_right = self.getIncidentColumn(theta, offsetByWidth=False)
		
	def getCOPRelativeAngleLeft(self):
		return self.cop_rtheta_left

	def getCOPRelativeAngleRight(self):
		return self.cop_rtheta_right
		
	def setPositionInODSImageLeft(self, xnorm):
		self.odsleft_xnorm = xnorm

	def setPositionInODSImageRight(self, xnorm):
		self.odsright_xnorm = xnorm

	def getPositionInODSImageLeft(self):
		return self.odsleft_xnorm

	def getPositionInODSImageRight(self):
		return self.odsright_xnorm
		
	def getGlobalAngleOfPixel(self, cam_pos, pixel):
		cam_coord=getRayForPixel(self, pixel[0], pixel[1])	
		world_coord_homo=np.dot(self.getExtrinsics, cam_coord)
		homo=world_coord_homo/world_coord_homo[3]
		world_coord=[homo[0], homo[1], homo[2]]
		

# end class Camera 


class CameraCollection():

	def __init__(self):
		self.camera_collection = []
		self.num_cameras = 0
		self.planar_camera_positions = None
		self.init_complete = False

	def sanityCheck(self):
		if not self.init_complete:
			raise RuntimeError('Camera collection is not initialized')

	def addCamera(self, camera):
		self.camera_collection.append(camera)
		self.num_cameras = self.num_cameras + 1


	def readAllCameras(self, yaml):
		calib_data = load_camera_calibration_data(yaml)
		num_cameras = len(calib_data)

		for i in range(num_cameras):
			cam_name = 'cam' + str(i)
			c = Camera()
			c.loadCameraFromYaml(calib_data, cam_name)
			self.addCamera(c)


	def __getitem__(self, key):
		return self.camera_collection[key]


	def __len__(self):
		return self.num_cameras


	def updateCameraXZLocations(self, origin):
		if len(origin) != 3:
			raise RuntimeError('Only 3D co-ordinates supported. Origin must be a 3D vector.')

		self.planar_camera_positions = np.zeros((self.num_cameras, 2), dtype='float32')
		# First camera is considered to be at the origin by default
		self.planar_camera_positions[0, :] = [origin[0], origin[2]]
		ordering=[0,1,2,3,8,9,7,6,4,5]
		# ordering = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
		for i in range(1, self.num_cameras):
			#ref = np.asarray([0, 0], dtype='float32')
			# Reference camera for the current camera is the previous camera (according to the .yaml file)
			cam_i=ordering[i]
			cam_i_old=ordering[i-1]
			ref_cam = self.camera_collection[i-1].getExtrinsics()
			#ref_cam = self.camera_collection[cam_i_old].getExtrinsics()
			ref = [ref_cam[0][3], ref_cam[2][3]]
			# Extract [x,z] values from the current camera extrinsics and add it with the reference.
			# First find -R^T*T for the reference camera. Then find -R^T*T for the current camera
			R=np.zeros((3, 3), dtype='float32')
			t=np.zeros((3, 1), dtype='float32')
			
			#VERY ugly matrix assignment, I am sorry, I didn't find a nicer way :(
			R[0][0]=ref_cam[0][0]
			R[1][0]=ref_cam[1][0]
			R[2][0]=ref_cam[2][0]
			R[0][1]=ref_cam[0][1]
			R[1][1]=ref_cam[1][1]
			R[2][1]=ref_cam[2][1]
			R[0][2]=ref_cam[0][2]
			R[1][2]=ref_cam[1][2]
			R[2][2]=ref_cam[2][2]
			# R = ref_cam[0:3, 0:3]
			R=np.transpose(R)
			# print(R)
			t[0]=ref_cam[0][3]
			t[1]=ref_cam[1][3]
			t[2]=ref_cam[2][3]
			# t = ref_cam[0:3, 2]
			#print(t)
			ref=np.dot(-R,t)
			#print(ref)

			# Repeat for the current camera.
			cam = self.camera_collection[i].getExtrinsics()
			R2=np.zeros((3, 3), dtype='float32')
			t2=np.zeros((3, 1), dtype='float32')
			
			#VERY ugly matrix assignment, I am sorry, I didn't find a nicer way :(
			R2[0][0]=cam[0][0]
			R2[1][0]=cam[1][0]
			R2[2][0]=cam[2][0]
			R2[0][1]=cam[0][1]
			R2[1][1]=cam[1][1]
			R2[2][1]=cam[2][1]
			R2[0][2]=cam[0][2]
			R2[1][2]=cam[1][2]
			R2[2][2]=cam[2][2]
			R2=np.transpose(R2)
			# print(R)
			t2[0]=cam[0][3]
			t2[1]=cam[1][3]
			t2[2]=cam[2][3]
			#print(t)
			pos=np.dot(-R2,t2)
			self.planar_camera_positions[cam_i, :] = ref[0]+pos[0], ref[2]+pos[2]
	

	def getCameraCentresXZ(self, origin):
		self.updateCameraXZLocations(origin)
		return self.planar_camera_positions


	def getViewingCircleCentre(self):
		# Uncomment following line to set the viewing circle centre to the average of the cameras.
		# This works when all cameras are properly aligned in a circle.
		# centre = np.sum(self.planar_camera_positions, axis=0)/self.num_cameras
		# Fit a circle to locations of cameras 0, 2 and 8
		if self.planar_camera_positions is None:
			self.updateCameraXZLocations([0, 0, 0])
		centre = fitCircleTo3Points(self.planar_camera_positions[0, :], 
			self.planar_camera_positions[2, :], self.planar_camera_positions[8, :])
		return centre

	def getViewingCircleRadius(self):
		centre = self.getViewingCircleCentre()
		return np.linalg.norm(self.planar_camera_positions[0, :]-centre)

	def getNumCameras(self):
		return self.num_cameras

	def visualizeCameras(self, origin):
		self.updateCameraXZLocations(origin)
		centre = self.getViewingCircleCentre()
		# test IPD
		ipd = self.getViewingCircleRadius()/2
		# Plot camera locations with their names
		fig, ax = pyplt.subplots()
		ax.scatter(self.planar_camera_positions[:, 0], self.planar_camera_positions[:, 1])
		ax.hold('on')

		# Plot cameras
		for i in range(self.num_cameras):
			ax.annotate(self.camera_collection[i].camera_name, (self.planar_camera_positions[i, 0], 
				self.planar_camera_positions[i, 1]))

		# Plot viewing circle along with its centre
		ax.scatter(centre[0], centre[1], color='red')
		ax.annotate('Centre', (centre[0], centre[1]))

		viewing_circle = getCirclePoints(centre, ipd)
		print(ipd)
		ax.scatter(viewing_circle[:, 0],viewing_circle[:, 1], color='red')
		
		# Plot left eye tangent points for the left eye
		for i in range(self.num_cameras):
			point_right = genPointOnViewingCircle(centre, self.planar_camera_positions[i, :], ipd)
			point_left = genPointOnViewingCircle(centre, self.planar_camera_positions[i, :], ipd, eye=-1)
			ax.scatter(point_right[0], point_right[1],color='orange')
			ax.annotate(str(i) + 'R', (point_right[0], point_right[1])
				, xytext=(point_right[0]+0.0001, point_right[1]+0.0001))
			ax.scatter(point_left[0], point_left[1],color='green')
			ax.annotate(str(i) + 'L', (point_left[0], point_left[1]))

		pyplt.show()



def load_camera_calibration_data(file_name):
	with open(file_name, 'r') as stream:
		try:
			calib_data = yaml.load(stream)
		except Exception as e:
			raise RuntimeError('Something bad happened when loading the .yaml file')

		return calib_data

