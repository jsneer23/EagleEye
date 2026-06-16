from src.analysis.brownout import BrownoutCheck
from src.analysis.can import CanUtilizationCheck
from src.parsers.wpilog_parser import LogParser
from src.tests.util import print_to_terminal

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
    print_to_terminal(rio_can_check)
    print_to_terminal(canivore_can_check)
    print_to_terminal(brownout_check)
