from src.analysis.util import Check, CheckResult, Context

class InitLogReportCheck(Check):

    def __init__(
        self,
    ) -> None:

        self.id = f"init"
        self.name = f"CAN Utilization - {bus_label}"
        self.signal_name = signal_name
        self.bus_label = bus_label
        self.warn = warn
        self.warn_peak = warn_peak
        self.sustained = sustained

    def run(self, ctx: Context) -> CheckResult: