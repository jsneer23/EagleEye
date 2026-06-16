from src.analysis.brownout import BrownoutCheck
from src.analysis.can import CanUtilizationCheck
from src.parsers.wpilog_parser import LogParser

if __name__ == "__main__":
    '''
    main function for testing this class piecemeal
    '''
    import sys

    parser = LogParser(sys.argv[1])
    signals = parser.parse_data()
    rio_can_check = CanUtilizationCheck("/Robot/SystemStats/CANBus/Utilization", "rio").run(signals)
    canivore_can_check = CanUtilizationCheck(
                            "/Robot/Canivore/Canivore Bus Utilization", "canivore").run(signals)
    brownout_check = BrownoutCheck().run(signals)
    print(rio_can_check)
    print(canivore_can_check)
    print(brownout_check)
