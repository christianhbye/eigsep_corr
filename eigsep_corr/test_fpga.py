from eigsep_corr.fpga import EigsepFpga

eig_fpga = EigsepFpga("10.10.237", "eigsep_fengine_.fpg")
eig_fpga.fpga.write_int("corr_acc_len", 2**28)
eig_fpga.fpga.write_int("corr_scalar", 2**9)
eig_fpga.test_corr_noise()

