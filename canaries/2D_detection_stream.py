import argparse as argparse
import asyncio

import cv2
import datetime
import numpy as np
from utils import Fps

from PIL import ImageDraw
from viam.components.camera import Camera
from viam.robot.client import RobotClient
from viam.rpc.dial import Credentials, DialOptions

import logging
import requests

parser = argparse.ArgumentParser(description="Displays a 2D image stream")

parser.add_argument('--payload', type=str, required=True, help='the credential')
parser.add_argument('--address', type=str, required=True, help='address of the robot (IP address, URL, etc.)')

parser.add_argument('--resolution', nargs=2, type=int, required=True, metavar=('width', 'height'), help='the size of the display window')
parser.add_argument('--coordinates', nargs=2, type=int, default=(0, 0), metavar=('x', 'y'), help='the xy-coordinates of the display window')

parser.add_argument('--cam', type=str, required=True, metavar='CAMERA_NAME', help='the name of the camera')
parser.add_argument('--webhook', type=str, help='the webhook to send logging info')

args = parser.parse_args()


async def connect():
    logging.info("connecting to robot client")
    creds = Credentials(
        type='robot-location-secret',
        payload=args.payload)
    opts = RobotClient.Options(
        refresh_interval=0,
        dial_options=DialOptions(credentials=creds)
    )
    return await RobotClient.at_address(args.address, opts)


async def close_robot(robot):
    if robot:
        logging.info("closing robot")
        await robot.close()
        logging.info("robot closed")


async def detection_stream(robot):
    fps = Fps()
    transform_cam_name = args.cam
    transform = Camera.from_robot(robot, transform_cam_name)
    logging.info(f"found camera {transform_cam_name}")
    while True:
        detect_img = await transform.get_image()
        fps.record()

        draw = ImageDraw.Draw(detect_img)
        draw.rectangle((0, 0, 75, 25), outline='black')
        draw.text(xy=(18, 7.5), text=f'{fps.get()} FPS', fill='white')

        pix = cv2.cvtColor(np.array(detect_img, dtype=np.uint8), cv2.COLOR_RGB2BGR)

        window_name = 'Detections'
        cv2.namedWindow(window_name, cv2.WINDOW_GUI_NORMAL)
        cv2.resizeWindow(window_name, args.resolution[0], args.resolution[1])
        cv2.moveWindow(window_name, args.coordinates[0], args.coordinates[1])
        cv2.imshow(window_name, pix)
        cv2.waitKey(1)


async def main():
    robot = None
    exit_status = 0
    try:
        robot = await connect()
        logging.info("finished connecting to robot client")
        await detection_stream(robot)
    except Exception as e:
        logging.info(f"caught exception '{e}'")
        if args.webhook is not None:
            body = {"text": f'{e}'}
            requests.post(args.webhook, json=body)
        logging.info(f"caught exception '{e}'")
        exit_status = 1
    finally:
        await close_robot(robot)
    logging.info(f'exiting with status {exit_status}')
    exit(exit_status)


if __name__ == '__main__':
    logging.basicConfig(
        filename=f'/tmp/canary_logs_detections_{datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")}.txt',
        encoding='utf-8',
        level=logging.INFO,
        filemode='w',
        force=True
    )

    asyncio.run(main())