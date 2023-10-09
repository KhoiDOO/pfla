import os 
import json

if __name__ == "__main__":
    # run_file = os.getcwd() + "/runv2.sh"
    sweep_file = os.getcwd() + "/sweep.json"
    
    sweep_data = json.load(open(sweep_file, mode='r'))
    
    algo = sweep_data["-algo"] 
    ds = sweep_data["-data"]
    nc = sweep_data["-nc"]
    go = sweep_data["-go"]
    
    for _algo in algo:
        cmd_lst = []
        run_file = os.getcwd() + f"/{_algo}.sh"
        for _ds in ds:
            for _nc in nc:
                if _nc["nc"] == 20 and _ds["name"] in ["Cifar10", "Cifar100", "mnist"]:
                    continue
                else:
                    cmd_lst.append(
                        f"python -u main.py -lbs 16 -nc {_nc['nc']} -jr 1 -nb 10 -data {_ds['name']} -nb {_ds['#cls']} -m {_ds['-m']} -algo {_algo} -gr {_nc['gr']} -did 0 -bt 0.001 -go train -fceal\n"
                    )
                        
        with open(run_file, mode='w') as file:
            file.writelines(
                cmd_lst
            )
            file.close()