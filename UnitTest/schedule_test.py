import sys
sys.path.append("../")
import schedule


def main():
    s = schedule.Scheduler()
    s.run()


if __name__ == '__main__':
    main()
