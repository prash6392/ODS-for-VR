import cv2
import matplotlib.pyplot as plt
import numpy as np


class OpticalFlowCalculator:
	"""
	Sasha's implementation of optical flow packaged into a class.
	"""
	def __init__(self):
		pass

	def calculateFlow(self, current_f, next_f):
		cf = cv2.cvtColor(current_f, cv2.COLOR_BGR2GRAY)
		nf = cv2.cvtColor(next_f, cv2.COLOR_BGR2GRAY)
		flow = cv2.calcOpticalFlowFarneback(cf, nf, None, 0.5, 3, 15, 3, 5, 1.2, 0)
		return flow

	def getFlowInHSV(self, flow):
		h, w = flow.shape[:2]
		fx, fy = flow[:,:,0], flow[:,:,1]
		ang = np.arctan2(fy, fx) + np.pi
		v = np.sqrt(fx*fx+fy*fy)
		hsv = np.zeros((h, w, 3), np.uint8)
		hsv[...,0] = ang*(180/np.pi/2)
		hsv[...,1] = 255
		hsv[...,2] = np.minimum(v*4, 255)
		bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
		return bgr

	def warpImageWithFlow(self, img, flow):
		h, w = flow.shape[:2]
		flow = -flow
		# print(np.arange(w).shape)
		flow[:,:,0] += np.arange(w)
		flow[:,:,1] += np.arange(h)[:,np.newaxis]
		res = cv2.remap(img, flow, None, cv2.INTER_LINEAR)
		return res

	def showQuiverPlot(self, flow):
		rows = flow.shape[0]
		cols = flow.shape[1]
		X, Y = np.meshgrid(np.arange(0, rows), np.arange(0, cols))
		U = flow[:, :, 1]*-1
		V = flow[:, :, 0]*-1
		plt.figure()
		plt.title('Flow vectors')
		Q = plt.quiver(Y, X, V, U, pivot='mid', units='width')
		plt.show()

# End class OpticalFlow

