import time
from flcore.clients.clientrecon import clientRecon
from flcore.servers.serverbase import Server
from threading import Thread
import torch
import torch.nn.functional as F
from collections import OrderedDict
import copy
import numpy as np

class Recon(Server):
    def __init__(self, args, times):
        super().__init__(args, times)

        # select slow clients
        self.set_slow_clients()
        self.set_clients(clientRecon)

        print(f"\nJoin ratio / total clients: {self.join_ratio} / {self.num_clients}")
        print("Finished creating server and clients.")

        # self.load_model()
        self.Budget = []
        self.network = self.clients[0].model.cuda()
        self.layers_dict = self.clients[0].get_layers() #_get_layers
        self.layers_name = list(self.layers_dict.keys())
        self.grad_dims = self.clients[0].get_grad_dims()
        self.layer_wise_angle = OrderedDict()
        self.initilize_grads()
        
        self.S_score = OrderedDict()
        for name in self.layers_name:
            self.S_score[name] = 0
        self.s = args.s_score
        #self.sub_method = args.sub_method
        #self.mini_rounds = args.mini_rounds
        #self.mini_rounds = int(self.global_rounds/2)
        self.mini_rounds = 30
        self.top_k = args.top_k
            
    def initilize_grads(self):
        """
        Initialize the gradients. Need to be called before every training iteration.
        """
        self.grads = torch.zeros(sum(self.grad_dims), self.num_join_clients).cuda()

    def train(self):
        for i in range(self.mini_rounds+1):
            grad_all = []
            s_t = time.time()
            self.selected_clients = self.select_clients()
            self.send_models()
            
            for name in self.layers_name:
                self.layer_wise_angle[name] = []

            if i%self.eval_gap == 0:
                print(f"\n-------------Round number: {i}-------------")
                print("\nEvaluate global model")
                self.evaluate()

            for client in self.selected_clients:
                client.train()
                grad = client.grad2vec_list()
                grad = client.split_layer(grad_list=grad, name_dict=self.layers_dict)
                grad_all.append(grad)
                for param in client.model.parameters():
                    if param.grad is not None:
                        param.grad.zero_()
            
            # The length of the layers
            length = len(grad_all[0])       # number of layers

            """
            pair_grad = {
                Layer 1: [
                    Users 1-2, User 1-3, ... ,User (N-1)-N
                ],
                Layer 2: [
                    Users 1-2, User 1-3, ... ,User (N-1)-N
                ],
                ....
                Layer L: [
                    Users 1-2, User 1-3, ... ,User (N-1)-N
                ],
            }
            """
            # get the pair-wise gradients
            pair_grad = []
            for i in range(length):
                temp = []
                for j in range(self.num_join_clients):
                    temp.append(grad_all[j][i])
                temp = torch.stack(temp)
                pair_grad.append(temp)

            """
            layer_wise_cos = {
                Layer 1: [
                    Users 1-2, User 1-3, ... ,User (N-1)-N
                ],
                Layer 2: [
                    Users 1-2, User 1-3, ... ,User (N-1)-N
                ],
                ....
                Layer L: [
                    Users 1-2, User 1-3, ... ,User (N-1)-N
                ],
            }
            """
            # get all cos<g_i, g_j>
            for i, pair in enumerate(pair_grad):
                layer_wise_cos = self.pair_cos(pair).cpu()
                self.layer_wise_angle[self.layers_name[i]].append(layer_wise_cos)
                
            """ Calculate S-conflict scores for all users """
            
            for layer, value in self.layer_wise_angle.items():
                count = np.sum([tensor < self.s for tensor in value[0]])
                self.S_score[layer] += count
            
                    
                # Loops over all layers
                    # Compute number of cos < 0 -> S
                    # Sum S-conflict scores: np.sum(S)  || Sum over users' layer-wise gradient

                # Top K layers with highest score -> Get index of layers

                # -> Set of conflict layers L1     (K layers with highest scores)
                # -> Set of non-conflict layers L2 (L-K layers)
            """  """
            
            # self.overwrite_grad(g)
            
            self.receive_models()
            if self.dlg_eval and i%self.dlg_gap == 0:
                self.call_dlg(i)

            # Global Aggregation of round N only non-conflict layers L1
            # self.aggregate_parameters_recon(L2)
            self.aggregate_parameters()

            self.Budget.append(time.time() - s_t)
            print('-'*25, 'time cost', '-'*25, self.Budget[-1])

            if self.auto_break and self.check_done(acc_lss=[self.rs_test_acc], top_cnt=self.top_cnt):
                break
        
        print('-'*30)
        print(self.S_score)
        top_k_items = sorted(self.S_score.items(), key=lambda x: x[1], reverse=True)[:self.top_k]
        top_k_layer = [key for key, _ in top_k_items]
        print( top_k_layer)
        print('-'*30)
        
        for i in range(self.mini_rounds+1, self.global_rounds+1):
            s_t = time.time()
            self.selected_clients = self.select_clients()
            self.send_model_recon(top_k_layer)

            if i%self.eval_gap == 0:
                print(f"\n-------------Round number: {i}-------------")
                print("\nEvaluate global model")
                self.evaluate()

            for client in self.selected_clients:
                client.train()

            # threads = [Thread(target=client.train)
            #            for client in self.selected_clients]
            # [t.start() for t in threads]
            # [t.join() for t in threads]

            self.receive_models()
            if self.dlg_eval and i%self.dlg_gap == 0:
                self.call_dlg(i)
            self.aggregate_parameters()

            self.Budget.append(time.time() - s_t)
            print('-'*25, 'time cost', '-'*25, self.Budget[-1])

            if self.auto_break and self.check_done(acc_lss=[self.rs_test_acc], top_cnt=self.top_cnt):
                break
        
        print("\nBest accuracy.")
        # self.print_(max(self.rs_test_acc), max(
        #     self.rs_train_acc), min(self.rs_train_loss))
        print(max(self.rs_test_acc))
        print("\nAverage time cost per round.")
        print(sum(self.Budget[1:])/len(self.Budget[1:]))

        self.save_results()
        self.save_global_model()

        if self.num_new_clients > 0:
            self.eval_new_clients = True
            self.set_new_clients(clientRecon)
            print(f"\n-------------Fine tuning round-------------")
            print("\nEvaluate new clients")
            self.evaluate()
            
    def pair_cos(self, pair):
        length = pair.size(0)

        dot_value = []
        for i in range(length - 1):
            for j in range(i + 1, length):
                dot_value.append(self.cos(pair[i], pair[j]))

        dot_value = torch.stack(dot_value).view(-1)
        return dot_value
    def cos(self, t1, t2):
        t1 = F.normalize(t1, dim=0)
        t2 = F.normalize(t2, dim=0)

        dot = (t1 * t2).sum(dim=0)

        return dot
    
    def overwrite_grad(self, newgrad):
        newgrad = newgrad * self.num_join_clients  # to match the sum loss
        cnt = 0
        for name, param in self.network.named_parameters():
            beg = 0 if cnt == 0 else sum(self.grad_dims[:cnt])
            en = sum(self.grad_dims[:cnt + 1])
            this_grad = newgrad[beg: en].contiguous().view(param.data.size())
            param.grad = this_grad.data.clone()
            cnt += 1

    def aggregate_parameters_recon(self, L2):
        # L2: 1 list of layer index
        assert (len(self.uploaded_models) > 0)

        self.global_model = copy.deepcopy(self.uploaded_models[0])
        for param in self.global_model.parameters():
            param.data.zero_()

        # for w, client_model in zip(self.uploaded_weights, self.uploaded_models):
            # for layer in client_model parameters:
                # if layer is existed in L2:
                    # self.add_parameters(w, client_model)
                # else:
                    # pass
    def send_model_recon(self, layer):
        assert (len(self.clients) > 0)

        for client in self.clients:
            start_time = time.time()
            
            client.set_parameters_recon(self.global_model, layer)

            client.send_time_cost['num_rounds'] += 1
            client.send_time_cost['total_cost'] += 2 * (time.time() - start_time)