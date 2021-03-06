import sys
import h5py
import getopt
import timeit
import os
import numpy as np


from math import sqrt

#sys.path.append(os.path.dirname(os.path.realpath(__file__)))
import helper
from helper import expect_squiggle_dict
from helper import parse_candidate_file


from dtw import dtw_local_alignment_max_mean as dtw_mean
#from dtw_cy.dtw import dtw_local_alignment_max_sum as dtw_sum
from dtw import dtw_local_alignment_max_sum as dtw_sum
from dtw import dtw_global_alignment_max_sum as dtw_global
from dtw import dtw_local_alignment_max_sum_band_flipped as dtw_band
from dtw import dist_to_likelihood, dist_to_likelihood_flipped_time_serie,dist_to_likelihood_flipped_new_path,dist_to_likelihood_flipped

def parse_arg():
    def print_help():
        print("\n\nUsage: python {} [OPTIONS] <fast5 filename>".format(argv[0]))
        print("Options:\n\tIndexing:")
        print('\t\t-c INT\tcandidate file name (required)')
        print("\t\t-o INT\toutput csv name, default: 'Untitled'")
        print('\t\t-T \tNumber of events trimmed from scrappie model')
        print('\t\t-t \tNumber of samples trimmed from raw signal')
     
        return None

    argv = sys.argv
    if len(argv) <= 2:     
        print_help()       # print help doc when no command line args provided
        sys.exit(0)
    
    try: 
        opts, args = getopt.getopt(argv[1:],"ho:c:T:t:ab:",
                    ["help=","output_csv=", "candidate_file=",\
                    "trim_model=","trim_signal=","dtw_adj","bandwidth="])
    except getopt.GetoptError:
        print_help()
        sys.exit(0)

    output_file = "Untiled"
    try:
        fast5_filename = args[0]
    except:
        print("InputError: missing fast5 file name!")
        sys.exit(0)

    # DEFAULT VALUE
    trim_signal = 0
    trim_model = 4
    dtw_adj = False
    bandwidth = False

    for opt, arg in opts:
        if opt in ('-h', "--help"):
            print_help()
            sys.exit(0)
        elif opt in ("-o", "--output_csv"):
            output_file = arg
        elif opt in ("-c", "--candidate_file"):
           candidate_file = arg
        elif opt in ("-T", "--trim_model"):
           trim_model = int(arg)
        elif opt in ("-t", "--trim_signal"):
           trim_signal = int(arg)
        elif opt in ("-a", "--dtw_adj"):
           dtw_adj = True
        elif opt in ("-b", "--bandwidth"):
           bandwidth = float(arg)

    # choose the version of dtw (sum: minimize the sum of cost for the path)
    dtw_local_alignment = dtw_mean if dtw_adj else dtw_sum
    
    if bandwidth:
        def dtw_local_alignment(long, short, dist_type = None, upper = np.inf):
            return dtw_band(long=long, short=short, band_prop = bandwidth,\
            dist_type = dist_type, upper = upper)
    
    return fast5_filename, output_file, candidate_file,\
     dtw_local_alignment, trim_model, trim_signal

def main():
    fast5_filename, output_file, candidate_file, \
        dtw_local_alignment, trim_model, trim_signal = parse_arg()
    
    # get read id
    #########################################################
    #read_id  = helper.Fast5Class(fast5_filename).get_read_id()
    #########################################################
   
    outf = open(output_file,'w')
    '''
    outf.write("read id")
    for i in range(len(sequence)):
        outf.write(",z_score{},log_likelihood{},manhattan{}".format(i+1,i+1,i+1))
    
    outf.write('\n'+ fast5_filename)
    '''

    candidates = parse_candidate_file(candidate_file)

    try:
        strand = helper.Fast5Class(fast5_filename).get_alignment(
            "mapping_info")["mapped_strand"]
    except:
        sys.exit(0)


    for candidate in candidates:
        outf.write(fast5_filename + ',' + strand + ',')
        
        # get signal
        signal = helper.get_junction_signal_by_pos(
            fast5 = fast5_filename, start_pos = candidate.start + trim_signal,
             end_pos = candidate.end - trim_signal)



        if not len(signal):
            for i in range(len(candidate.sequences)):
                outf.write(",NA,NA,NA")
            outf.write("\n")
            print("read discarded")
            continue
        # take reverse compliment seq if nesseccary
        
        if strand == "-":
            candidate.sequences = [helper.reverse_complement(s)
             for s in candidate.sequences]

########################################delete later######################################
 #       with open("squiggle.csv", 'a') as squiggle_f:
   #         squiggle_f.write(','.join([str(x) for x in signal]) + '\n')
   #     with open("candidate.csv", 'a') as candidate_f:
   #         candidate_f.write(read_id + ',' + ','.join(candidate.sequences) + '\n')
   #     continue
##########################################################################################

        # Normalisation
        #signal = helper.normalization(signal,"z_score") # "median_shift" or "z_score"

        model_dic = expect_squiggle_dict(candidate.sequences, trim = trim_model)
        
        dtw_long = np.array(signal, float)

        for key in candidate.sequences:

            dtw_short = np.array(model_dic[key],float)
            #dtw_short[:,0] = helper.normalization(dtw_short[:,0], "z_score")
            #dtw_short[:,1] = dtw_short[:,1]/sqrt(np.std(dtw_short[:,0]))

            #print("dtw_short")
            dtw_short = np.array(dtw_short)
            #np.random.shuffle(dtw_short)
            #print("Input queried signal: " + '\t'.join([str(i) for i in dtw_long]))

            #print("\n\n\nInput model: " + '\t'.join([str(i) for i in dtw_short]))

            #print("\n\n\nRunning DTW...")

            timer_start = timeit.default_timer()
            #dtw_long = np.repeat(dtw_long,3)
            #dtw_long = dtw_long[abs(dtw_long)-3 < 0]
            path1 , score1 = 'NA','NA'
            #path1 , score1 = dtw_local_alignment(dtw_long, dtw_short, dist_type = "z_score")[0:2]
            #path2 , score2 = 'NA','NA'
            path2 , score2 = dtw_local_alignment(dtw_long, dtw_short, dist_type = "log_likelihood")[0:2]
            #likelihood, unmatched = dist_to_likelihood(dtw_long, dtw_short, path2, dist_type = "log_likelihood")
            likelihood, unmatched = dist_to_likelihood_flipped(dtw_short, dtw_long, path2, dist_type = "log_likelihood")    
            #new_path2, likelihood=dist_to_likelihood_flipped_new_path(dtw_short, dtw_long, path2, dist_type = "log_likelihood")
            path3 , score3 = 'NA','NA'
            #path3 , score3 = dtw_local_alignment(dtw_long, dtw_short, dist_type = 'manhattan')[0:2]
            #outf.write(',{},{},{}'.format(score1,score2,score3))
            outf.write(',{},{},{}'.format(likelihood,score2,unmatched))
            timer_stop = timeit.default_timer()
            runtime = timer_stop - timer_start

            # ploting 
            if False:
                for score, path in (score1, path1), (score2, path2), \
                (score3, path3):
                    helper.plot_dtw_alignment(figure_name = "Untitled", \
                    figure_title = "Untitled" , long_seq = dtw_long, \
                    short_seq = dtw_short, dtw_path = path, dtw_score = score, \
                    show_sd = True, figsize=(10,7))

        outf.write('\n')

if __name__ == "__main__":
    main()
