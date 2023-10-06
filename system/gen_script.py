import os 
import json

if __name__ == "__main__":
    run_file = os.getcwd() + "/runv2.sh"
    sweep_file = os.getcwd() + "/sweep.json"
    
    sweep_data = json.load(open(sweep_file, mode='r'))
    
    algo = sweep_data["-algo"] 
    ds = sweep_data["-data"]
    nc = sweep_data["-nc"]
    go = sweep_data["-go"]
    
    cmd_lst = []
    
    for _algo in algo:
        for _ds in ds:
            for _nc in nc:
                for _go in go:
                    cmd_lst.append(
                        f"python -u main.py -lbs 16 -nc {_nc} -jr 1 -nb 10 -data {_ds['name']} -nb {_ds['#cls']} -m {_ds['-m']} -algo {_algo} -gr 100 -did 0 -bt 0.001 -go {_go} -fceal\n"
                    )
                        
    with open(run_file, mode='w') as file:
        file.writelines(
            cmd_lst
        )
        file.close()