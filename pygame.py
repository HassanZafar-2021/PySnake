import pygame
import time 
import random

# Snake Game using Pygame

snake_speed = 15

# Window size
window_x = 720
window_y = 480

# colors

black = pygame.Color(0, 0, 0)
red = pygame.Color(255, 0, 0)
green = pygame.Color(0, 255, 0)

# Initializing pygame

pygame.init()
pygame.display.set_caption("Snake Game")

