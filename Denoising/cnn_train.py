#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import math
import numpy as np
import torch
import torch.nn as nn
from torch.nn import init
import torch.nn.parallel
import torch.backends.cudnn as cudnn
import torch.optim as optim
import torch.utils.data
import torchvision.datasets as dset
import torchvision.transforms as transforms
import torchvision.utils as vutils
from torch.autograd import Variable
import random
from skimage.measure import compare_psnr
import os

from cnn_model import CGP2CNN_autoencoder


def weights_init(m):
    classname = m.__class__.__name__
    if classname.find('Conv') != -1:
        m.weight.data.normal_(0.0, 0.02)
    elif classname.find('BatchNorm') != -1:
        m.weight.data.normal_(1.0, 0.02)
        m.bias.data.fill_(0)

def weights_init_normal(m):
    classname = m.__class__.__name__
    if classname.find('Conv2d') != -1:
        m.apply(weights_init_normal_)
    elif classname.find('Linear') != -1:
        init.uniform(m.weight.data, 0.0, 0.02)
    elif classname.find('BatchNorm2d') != -1:
        init.uniform(m.weight.data, 1.0, 0.02)
        init.constant(m.bias.data, 0.0)

def weights_init_normal_(m):
    classname = m.__class__.__name__
    if classname.find('Conv') != -1:
        init.uniform(m.weight.data, 0.0, 0.02)
    elif classname.find('Linear') != -1:
        init.uniform(m.weight.data, 0.0, 0.02)
    elif classname.find('BatchNorm2d') != -1:
        init.uniform(m.weight.data, 1.0, 0.02)
        init.constant(m.bias.data, 0.0)

def weights_init_xavier(m):
    classname = m.__class__.__name__
    if classname.find('Conv') != -1:
        init.xavier_normal(m.weight.data, gain=1)
    elif classname.find('Linear') != -1:
        init.xavier_normal(m.weight.data, gain=1)
    elif classname.find('BatchNorm2d') != -1:
        init.uniform(m.weight.data, 1.0, 0.02)
        init.constant(m.bias.data, 0.0)

def weights_init_kaiming(m):
    classname = m.__class__.__name__
    if classname.find('Conv') != -1:
        init.kaiming_normal(m.weight.data, a=0, mode='fan_in')
    elif classname.find('Linear') != -1:
        init.kaiming_normal(m.weight.data, a=0, mode='fan_in')
    elif classname.find('BatchNorm2d') != -1:
        init.uniform(m.weight.data, 1.0, 0.02)
        init.constant(m.bias.data, 0.0)

def weights_init_orthogonal(m):
    classname = m.__class__.__name__
    print(classname)
    if classname.find('Conv') != -1:
        init.orthogonal(m.weight.data, gain=1)
    elif classname.find('Linear') != -1:
        init.orthogonal(m.weight.data, gain=1)
    elif classname.find('BatchNorm2d') != -1:
        init.uniform(m.weight.data, 1.0, 0.02)
        init.constant(m.bias.data, 0.0)

def init_weights(net, init_type='normal'):
    print('initialization method [%s]' % init_type)
    if init_type == 'normal':
        net.apply(weights_init_normal)
    elif init_type == 'xavier':
        net.apply(weights_init_xavier)
    elif init_type == 'kaiming':
        net.apply(weights_init_kaiming)
    elif init_type == 'orthogonal':
        net.apply(weights_init_orthogonal)
    else:
        raise NotImplementedError('initialization method [%s] is not implemented' % init_type)


# __init__: load dataset
# __call__: training the CNN defined by CGP list
class CNN_train():
    def __init__(self, dataset_name, validation=True, verbose=True, imgSize=32, batchsize=16):
        # dataset_name: name of data set ('bsds'(color) or 'bsds_gray')
        # validation: [True]  model train/validation mode
        #             [False] model test mode for final evaluation of the evolved model
        #                     (raining data : all training data, test data : all test data)
        # verbose: flag of display
        self.verbose = verbose
        self.imgSize = imgSize
        self.validation = validation
        self.batchsize = batchsize
        self.dataset_name = dataset_name

        # load dataset
        if dataset_name == 'bsds' or dataset_name == 'bsds_gray':
            if dataset_name == 'bsds':
                self.n_class = 10
                self.channel = 3
                self.num_work = 2
                data_transform = transforms.Compose([transforms.RandomHorizontalFlip(),transforms.RandomCrop(64, 0), transforms.ToTensor()])
                test_data_transform = transforms.Compose([transforms.ToTensor()])
                if self.validation:
                    dataset = dset.ImageFolder(root='/dataset/BSDS500/color/train', transform=data_transform)
                    self.dataloader = torch.utils.data.DataLoader(dataset, batch_size=self.batchsize, shuffle=True, num_workers=int(self.num_work))
                    test_dataset = dset.ImageFolder(root='/dataset/BSDS500/color/val', transform=test_data_transform)
                    self.test_dataloader = torch.utils.data.DataLoader(test_dataset, batch_size=1, shuffle=True, num_workers=int(self.num_work))
                else:
                    dataset = dset.ImageFolder(root='/dataset/BSDS500/color/retrain', transform=data_transform)
                    self.dataloader = torch.utils.data.DataLoader(dataset, batch_size=self.batchsize, shuffle=True, num_workers=int(self.num_work))
                    test_dataset = dset.ImageFolder(root='/dataset/BSDS500/color/test', transform=test_data_transform)
                    self.test_dataloader = torch.utils.data.DataLoader(test_dataset, batch_size=1, shuffle=False, num_workers=int(self.num_work))
            elif dataset_name == 'bsds_gray':
                self.n_class = 10
                self.channel = 1
                self.num_work = 2
                data_transform = transforms.Compose([transforms.RandomHorizontalFlip(),transforms.RandomCrop(64, 0), transforms.ToTensor()])
                test_data_transform = transforms.Compose([transforms.ToTensor()])
                if self.validation: 
                    dataset = dset.ImageFolder(root='/dataset/BSDS500/gray/train', transform=data_transform)
                    self.dataloader = torch.utils.data.DataLoader(dataset, batch_size=self.batchsize, shuffle=True, num_workers=int(self.num_work))
                    test_dataset = dset.ImageFolder(root='/dataset/BSDS500/gray/val', transform=test_data_transform)
                    self.test_dataloader = torch.utils.data.DataLoader(test_dataset, batch_size=1, shuffle=True, num_workers=int(self.num_work))
                else:
                    dataset = dset.ImageFolder(root='/dataset/BSDS500/gray/retrain', transform=data_transform)
                    self.dataloader = torch.utils.data.DataLoader(dataset, batch_size=self.batchsize, shuffle=True, num_workers=int(self.num_work))
                    test_dataset = dset.ImageFolder(root='/dataset/BSDS500/gray/test', transform=test_data_transform)
                    self.test_dataloader = torch.utils.data.DataLoader(test_dataset, batch_size=1, shuffle=False, num_workers=int(self.num_work))
            print('train num    ', len(self.dataloader.dataset))
            print('val/test num ', len(self.test_dataloader.dataset))
        else:
            print('\tInvalid input dataset name at CNN_train()')
            exit(1)

    def __call__(self, cgp, gpuID, epoch_num=200, out_model='mymodel.model'):
        if self.verbose:
            print('GPUID    :', gpuID)
            print('epoch_num:', epoch_num)
        
        # model
        torch.backends.cudnn.benchmark = True
        model = CGP2CNN_autoencoder(cgp, self.channel, self.n_class, self.imgSize)
        model.cuda(gpuID)
        # Loss and Optimizer
        criterion = nn.MSELoss()
        criterion.cuda(gpuID)
        optimizer = optim.Adam(model.parameters(), lr=0.001, betas=(0.5, 0.999))
        input = torch.FloatTensor(self.batchsize, self.channel, self.imgSize, self.imgSize)
        input = input.cuda(gpuID)
        # Noise level
        std_list = [30,50,70]
        n = 50
        # for outputs
        if not os.path.exists('./outputs'):
            os.mkdir('./outputs')

        # Train loop
        for epoch in range(1, epoch_num+1):
            start_time = time.time()
            if self.verbose:
                print('epoch', epoch)
            train_loss = 0
            ite = 0
            for module in model.children():
                module.train(True)
            for _, (data, _) in enumerate(self.dataloader):
                if self.dataset_name == 'bsds_gray':
                    data = data[:,0:1,:,:] # for gray scale images
                data = data.cuda(gpuID)
                std = std_list[random.randint(0,len(std_list)-1)]
                for _ in range(1,n,1):
                    input.resize_as_(data).copy_(data)
                    input_ = Variable(input)
                    data_noise = self.gaussian_noise(input_, 0.0, std)
                    optimizer.zero_grad()
                    try:
                        output = model(data_noise, None)
                    except:
                        import traceback
                        traceback.print_exc()
                        return 0.
                    loss = criterion(output, input_)
                    train_loss += loss.data[0]
                    loss.backward()
                    optimizer.step()
                    if ite == 0:
                        vutils.save_image(data_noise.data, './noise_samples%d.png' % gpuID, normalize=False)
                        vutils.save_image(input_.data, './org_samples%d.png' % gpuID, normalize=False)
                        vutils.save_image(output.data, './output%d.png' % gpuID, normalize=False)
                ite += 1
            print('Train set : Average loss: {:.4f}'.format(train_loss))
            print('time ', time.time()-start_time)
            if self.validation:
                if epoch == epoch_num:
                    for module in model.children():
                        module.train(False)
                    t_loss = self.__test_per_std(model, criterion, gpuID, input, std_list)
            else:
                if epoch % 10 == 0:
                    for module in model.children():
                        module.train(False)
                    t_loss = self.__test_per_std(model, criterion, gpuID, input, std_list)
                if epoch == 200:
                    for param_group in optimizer.param_groups:
                        tmp = param_group['lr']
                    tmp *= 0.1
                    for param_group in optimizer.param_groups:
                        param_group['lr'] = tmp
                if epoch == 400:
                    for param_group in optimizer.param_groups:
                        tmp = param_group['lr']
                    tmp *= 0.1
                    for param_group in optimizer.param_groups:
                        param_group['lr'] = tmp
        # save the model
        torch.save(model.state_dict(), './model_%d.pth' % int(gpuID))
        return t_loss


    # generate gaussian noise
    def gaussian_noise(self, inp, mean, std):
        noise = Variable(inp.data.new(inp.size()).normal_(mean, std))
        noise = torch.div(noise, 255.0)
        return inp + noise

    # calc PSNR by using "compare_psnr of skimage.measure"
    def calcPSNR(self, image1, image2):
        image1 *= 255
        image2 *= 255
        image1[image1>255] = 255
        image1[image1<0] = 0
        image2[image2>255] = 255
        image2[image2<0] = 0
        return compare_psnr(image1, image2, data_range=255)

    # For validation/test
    def __test_per_std(self, model, criterion, gpuID, input, std_list):
        test_loss = 0
        total_psnr = 0
        for std in std_list:
            print('std', std)
            ite = 0
            psnr = 0
            psnr2 = 0
            psnr3 = 0
            for _, (data, _) in enumerate(self.test_dataloader):
                if self.dataset_name == 'bsds_gray':
                    data = data[:,0:1,:,:]
                data = data.cuda(gpuID)
                input.resize_as_(data).copy_(data)
                input_ = Variable(input, volatile=True)
                data_noise = self.gaussian_noise(input_, 0.0, std)
                try:
                    output = model(data_noise, None)
                except:
                    import traceback
                    traceback.print_exc()
                    return 0.
                loss = criterion(output, input_)
                psnr += -10 * math.log10(loss.data[0])
                test_loss += loss.data[0]

                # # PSNR
                # img1 = (output.data).cpu().numpy()
                # img2 = (input_.data).cpu().numpy()
                # imdf = img2*255.0 - img1*255.0
                # imdf = imdf ** 2
                # rmse = np.sqrt(np.mean(imdf))
                # psnr2 += 20 * math.log10(255.0/rmse)
                # psnr3 += self.calcPSNR(img2, img1)

                # save images
                vutils.save_image(output.data, './outputs/test_output_std%02d_%03d.png' % (int(std), int(ite)), normalize=False)
                vutils.save_image(data_noise.data, './outputs/test_output_std%02d_%03d_.png' % (int(std), int(ite)), normalize=False)
                vutils.save_image(input_.data, './outputs/test_output_std%02d_%03d__.png' % (int(std), int(ite)), normalize=False)
                ite += 1
            psnr /= (ite)
            # psnr2 /= (ite)
            # psnr3 /= (ite)
            test_loss /= (ite)
            total_psnr += psnr
            print('Test PSNR: {:.4f}'.format(psnr))
            # print('Test PSNR2: {:.4f}'.format(psnr2))
            # print('Test PSNR3: {:.4f}'.format(psnr3))
            print('Test loss : {:.4f}'.format(test_loss))

        total_psnr /= len(std_list)
        return total_psnr
