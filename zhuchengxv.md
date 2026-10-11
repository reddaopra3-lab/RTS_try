import sys
import pygame
from steel_river.config.settings import SCREEN_WIDTH, SCREEN_HEIGHT, FPS

def main():
    pygame.init()
    pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
    
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("钢河前线 - 本地多文件 RTS 重构版")
    clock = pygame.time.Clock()
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                
        screen.fill((28, 32, 40))
        pygame.display.flip()
        clock.tick(FPS)
        
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()