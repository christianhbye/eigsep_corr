import casperfpga
import casperfpga.synth
import hera_corr_f


class EigsepFpga:
    
    def __init__(self, ip, fpg_file=None):
        self.fpga = casperfpga.CasperFpga(ip)
        if fpg_file is not None:
            self.fpg_file = fpg_file
            self.fpga.upload_to_ram_and_program(self.fpg_file)
        self.synth = casperfpga.synth.LMX2581(self.fpga, "synth")
        self.adc = hera_corr_f.blocks.Adc(
            self.fpga, num_chans=2, resolution=8, ref=10,
        )
        self.adc.init(sample_rate=500)
        self.sync = hera_corr_f.blocks.Sync(self.fpga, "sync")

        self.autos = [0, 1, 2, 3, 4, 5]
        self.crosses = ["02", "13", "24", "35", "04", "15"]

    def initialize_fpga(self, corr_acc_len=2**28, corr_scalar=2**9):
        """
        Parameters that must be set for the correlator

        Parameters
        ----------
        corr_acc_len : int (power of 2)
            The accumulation length. Default value ensures that the
            corr_acc_cnt goes up by 1 per ~1 second
        corr_scalar : int (power of 2)
            Scalar that is multiplied to each correlation. Default value is
            2**9 since the values have 8 bits after the binary point,
            hence 2**9 = 1

        """
        self.fpga.write_int("corr_acc_len", corr_acc_len)
        self.fpga.write_int("corr_scalar", corr_scalar)
    
    def initialize_adc(self, sample_rate):
        self.adc.init(sample_rate=sample_rate)

    def synchronize(self):
        self.sync.arm_sync()
        for i in range(3):
            self.sync.sw_sync()

    def read_auto(self, N):
        """
        Read the Nth (counting from 0) autocorrelation spectrum
        """
        name = "corr_auto_%d_dout"%N
        spec = np.array(struct.unpack(">2048l", self.fpga.read(name, 8192)))
        return spec

    def read_cross(self, NM):
        """
        Read the NM cross correlation spectrum

        Parameters
        ----------
        NM : str
            Which correlation to read, e.g. "02". Assuming N<M.
        """
        name = "corr_cross_%s_dout"%NM
        spec = np.array(stuct.unpack(">4096l", self.fpga.read(name, 16384)))
        return spec

    def test_corr_noise(self):
        noise = hera_corr_f.blocks.NoiseGen(
            self.fpga, "noise", nstreams=len(self.autos)
        )
        noise.set_seed()  # all feeds get same seed
        inp = hera_corr_f.blocks.Input(
            self.fpga, "input", nstreams=2*len(self.autos)
        )
        inp.use_noise()
        self.synchronize()

        cnt = self.fpga.read_int("corr_acc_cnt")
        # ensure that all spectra are recorded at the same time
        while self.fpga.read_int("corr_acc_cnt") == cnt:
            pass
        auto_spec = [self.read_auto(N) for N in self.autos]
        cross_spec = [self.read_cross(NM) for NM in self.crosses]
        # read a second time and see we get all the same
        auto_spec2 = [self.read_auto(N) for N in self.autos]
        cross_spec2 = [self.read_cross(NM) for NM in self.crosses]
        assert np.all(auto_spec == auto_spec2)
        assert np.all(cross_spec == cross_spec2)
        # all spectra should be the same since the noise is the same
        assert np.all(auto_spec == auto_spec[0])
        assert np.all(cross_spec == cross_spec[0])
        # cross corr should have real part = autos and im part = 0
        assert np.all(cross_spec[0][::2] == auto_spec[0])
        assert np.all(cross_spec[0][1::2] == 0)

        # use a different seed for each stream
        for i in range(len(self.autos)):
            noise.set_seed(stream=i, seed=i)
        inp.use_noise()
        self.synchronize()
        cnt = self.fpga.read_int("corr_acc_cnt")
        while self.fpga.read_int("corr_acc_cnt") == cnt:
            pass
        auto_spec = [self.read_auto(N) for N in self.autos]
        cross_spec = [self.read_cross(NM) for NM in self.crosses]
        # some autos are hardwired to be the same (0 == 1, 2 == 3, 4 == 5)
        assert np.all(auto_spec[0] == auto_spec[1])
        assert np.all(auto_spec[2] == auto_spec[3])
        assert np.all(auto_spec[4] == auto_spec[5])
        # the others are different
        assert np.any(auto_spec[0] != auto_spec[2])
        assert np.any(auto_spec[0] != auto_spec[4])
        assert np.any(auto_spec[2] != auto_spec[4])
        # certain cross corrs must be the same by the above hardwiring
        assert np.all(cross_spec[0] == cross_spec[1])  # 02 == 13
        assert np.all(cross_spec[2] == cross_spec[3])  # 24 == 35
        assert np.all(cross_spec[4] == cross_spec[5])  # 04 == 15
        # the others are different
        assert np.any(cross_spec[0] != cross_spec[2])
        assert np.any(cross_spec[0] != cross_spec[4])
        assert np.any(cross_spec[2] != cross_spec[4])
        # there's no reason for all imag parts to be 0 anymore
        for i in range(3):
            assert np.any(cross[2*i][1::2] != 0)
