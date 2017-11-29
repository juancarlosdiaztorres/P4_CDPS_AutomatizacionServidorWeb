#!/usr/bin/python
import subprocess
import sys
from lxml import etree
import copy
import os

#Decision en funcion de parametros
if len(sys.argv) < 2:
	sys.stderr.write("No se introdujo bien la orden \n")
	sys.exit(-1)


#Codigo crear: Crea ficheros qcow2  y xml
def crear(nServer):

	currentPath = os.getcwd()
	print(currentPath)

	#Redes
	subprocess.call("sudo brctl addbr LAN1", shell=True)
	subprocess.call("sudo brctl addbr LAN2", shell=True)
	subprocess.call("sudo ifconfig LAN1 up", shell=True)
	subprocess.call("sudo ifconfig LAN2 up", shell=True)

	#Configuracion de red del host
	subprocess.call("sudo ifconfig LAN1 10.0.1.3/24", shell=True)
	subprocess.call("sudo ip route add 10.0.0.0/16 via 10.0.1.1", shell=True)

	currentPath = os.getcwd()
	subprocess.call("mkdir "+currentPath+"/mnt", shell=True)

	#Creacion cliente y asocio XML al mismo
	createNewVM("c1", "LAN1")
	subprocess.call("sudo virsh define c1.xml", shell=True)

	#Configuracion de red maquina virtual c1
	subprocess.call("sudo vnx_mount_rootfs -s -r c1.qcow2 mnt", shell=True)
	subprocess.call("echo c1 > "+currentPath+"/mnt/etc/hostname", shell=True) 
	f = open(""+currentPath+"/mnt/etc/network/interfaces", "w")
	f.write("auto eth0 \n")
	f.write("iface eth0 inet static \n")
	f.write("address 10.0.1.2 \n")
	f.write("netmask 255.255.255.0 \n")
	f.write("gateway 10.0.1.1 \n")
	f.close()
	f = open(""+currentPath+"/mnt/etc/sysctl.conf","w")
	f.write("net.ipv4.ip_forward = 1")
	f.close()

	fr = open(""+currentPath+"/mnt/etc/hosts", "r")
	lineas =  fr.readlines()
	fr.close()
	fw = open(""+currentPath+"/mnt/etc/hosts", "w")
	for line in lineas:
		if "127.0.1.1 cdps cdps" in line:
			fw.write("127.0.1.1 c1\n")
		else: 
			fw.write(line)
	fw.close()

	subprocess.call("sudo vnx_mount_rootfs -u mnt", shell=True)
	

	#Creacion LB 
	createLB()
	subprocess.call("sudo virsh define lb.xml", shell=True)	
	
	#Configuracion red LB
	subprocess.call("sudo vnx_mount_rootfs -s -r lb.qcow2 mnt", shell=True)
	subprocess.call("echo lb > "+currentPath+"/mnt/etc/hostname", shell=True)
	f = open(""+currentPath+"/mnt/etc/network/interfaces", "w")
	f.write("auto eth0 \n")
	f.write("iface eth0 inet static \n")
	f.write("address 10.0.1.1 \n")
	f.write("netmask 255.255.255.0 \n")
	f.write("gateway 10.0.1.1 \n")
	f.write("auto eth1 \n")
	f.write("iface eth1 inet static \n")
	f.write("address 10.0.2.1 \n")
	f.write("netmask 255.255.255.0 \n")
	f.write("gateway 10.0.2.1 \n")
	f.close()
	f = open(""+currentPath+"/mnt/etc/sysctl.conf", "w")
	f.write("net.ipv4.ip_forward=1  \n")
	f.close()

	fr = open(""+currentPath+"/mnt/etc/rc.local", "r")
	lineas =  fr.readlines()
	fr.close()
	fw = open(""+currentPath+"/mnt/etc/rc.local", "w")
	
	fw.write("#!/bin/sh\n")

		
	stg1 = "sudo xr -dr --server tcp:0:80 "
	stg2 = " --web-interface 0:8001"
	stg3 = ""
	for server in range(1, nServer + 1):
		stg3 = stg3 + " --backend 10.0.2.1" + str(server) + ":80"

	fw.write("service apache2 stop\n"+stg1+stg3+stg2+" &\n")

	fw.close()


	fr = open(""+currentPath+"/mnt/etc/hosts", "r")
	lineas =  fr.readlines()
	fr.close()
	fw = open(""+currentPath+"/mnt/etc/hosts", "w")
	for line in lineas:
		if "127.0.1.1 cdps cdps" in line:
			fw.write("127.0.1.1 lb\n")
		else: 
			fw.write(line)
	fw.close()

	#fw = open(""+currentPath+"/mnt/proc/sys/net/ipv4/ip_forward", "w")
	#fw.write("1")
	#fw.close()

	subprocess.call("sudo vnx_mount_rootfs -u mnt", shell=True)

	#Creacion servidores 
	for server in range(1, nServer + 1):
		createNewVM("s"+str(server), "LAN2")
		subprocess.call("sudo virsh define s"+str(server)+".xml", shell=True)

		#Ahora, para cada servidor, monto el sistema de ficheros
		subprocess.call("sudo vnx_mount_rootfs -s -r s"+ str(server)+".qcow2 mnt", shell=True)
		subprocess.call("echo s"+str(server)+" > "+currentPath+"/mnt/etc/hostname", shell=True)
		f = open(""+currentPath+"/mnt/etc/network/interfaces", "w")
		#f.write("auto lo \n")
		#f.write("iface lo inet loopback \n")
		f.write("auto eth0 \n")
		f.write("iface eth0 inet static \n")
		f.write("address 10.0.2.1"+str(server)+" \n")
		f.write("netmask 255.255.255.0 \n")
		f.write("gateway 10.0.2.1 \n")
		f.close()

		fw = open(""+currentPath+"/mnt/var/www/html/index.html", "w")
		fw.write("S"+str(server))
		fw.close()

		fr = open(""+currentPath+"/mnt/etc/hosts", "r")
		lineas =  fr.readlines()
		fr.close()
		fw = open(""+currentPath+"/mnt/etc/hosts", "w")
		for line in lineas:
			if "127.0.1.1 cdps cdps" in line:
				fw.write("127.0.1.1 s"+str(server)+"\n")
			else: 
				fw.write(line)
		fw.close()

		subprocess.call("sudo vnx_mount_rootfs -u mnt", shell=True)


	#Borrar el directorio
	subprocess.call("rmdir "+currentPath+"/mnt", shell=True)

	#Lanzamos el gestor de maquinas
	subprocess.call("sudo virt-manager", shell=True)


#Codigo arrancar: Arranca VM y consolas
def arrancar(vm):
	f = open("count.txt", "r")
	nServer = int(f.readline())
	f.close()
	
	if vm == "c1":
		#Arrancar cliente
		subprocess.call("sudo virsh start c1", shell=True)
		subprocess.call("xterm -rv -sb -rightbar -fa monospace -fs 10 -title 'c1' -e 'sudo virsh console c1' &", shell=True)
	elif  vm == "lb":
		#Arrancar lb
		subprocess.call("sudo virsh start lb", shell=True)
		subprocess.call("xterm -rv -sb -rightbar -fa monospace -fs 10 -title 'lb' -e 'sudo virsh console lb' &", shell=True)
	elif vm == "s0" or vm == "s1" or vm == "s2" or vm == "s3" or vm == "s4":
		#Arrancar servidores
		subprocess.call("sudo virsh start "+vm, shell=True)
		subprocess.call("xterm -rv -sb -rightbar -fa monospace -fs 10 -title '"+vm+"' -e 'sudo virsh console "+vm+"' &", shell=True)
	elif vm == "": 
		#Arrancar lb
		subprocess.call("sudo virsh start lb", shell=True)
		subprocess.call("xterm -rv -sb -rightbar -fa monospace -fs 10 -title 'lb' -e 'sudo virsh console lb' &", shell=True)

		#Arrancar cliente
		subprocess.call("sudo virsh start c1", shell=True)
		subprocess.call("xterm -rv -sb -rightbar -fa monospace -fs 10 -title 'c1' -e 'sudo virsh console c1' &", shell=True)

		#Arrancar servidores
		for server in range(1, nServer + 1):
			subprocess.call("sudo virsh start s"+str(server), shell=True)
			subprocess.call("xterm -rv -sb -rightbar -fa monospace -fs 10 -title 's"+str(server)+"' -e 'sudo virsh console s"+str(server)+"' &", shell=True)
	else:
		sys.stderr.write("No se pudo arrancar las VM")

#codigo parar:
def parar(vm):

	#Parar C1
	if vm == "c1":
		subprocess.call("sudo virsh shutdown c1", shell=True)

	#Parar LB
	elif vm == "lb":
		subprocess.call("sudo virsh shutdown lb", shell=True)

	#Parar uno de los servidores
	elif vm == "s0" or vm == "s1" or vm == "s2" or vm == "s3" or vm == "s4":
		#Consultar cuantos servidores hay
		f = open("count.txt", "r")
		nServer = int(f.readline())
		f.close()

		#Parar el servidor
		for server in range(1, nServer + 1):
			subprocess.call("sudo virsh shutdown "+vm, shell=True)

	#Parar todas las VMs
	elif vm == "":
		subprocess.call("sudo virsh shutdown c1", shell=True)
		subprocess.call("sudo virsh shutdown lb", shell=True)

		#Consultar cuantos servidores hay
		f = open("count.txt", "r")
		nServer = int(f.readline())
		f.close()

		#Parar todos los servidores
		for server in range(1, nServer + 1):
			subprocess.call("sudo virsh shutdown s"+str(server), shell=True)

	#Error de ejecucion
	else:
		sys.stderr.write("No se pudo parar las VM")


#Codigo destruir: Borrar ficheros y escenario
def destruir():

	#Borrar C1 y LB
	subprocess.call("sudo virsh destroy c1", shell=True)
	subprocess.call("sudo virsh destroy lb", shell=True)
	subprocess.call("sudo virsh undefine c1", shell=True)
	subprocess.call("sudo virsh undefine lb", shell=True)

	#Borrar ficheros asociados a C1 y LB
	subprocess.call("rm c1.xml", shell=True)
	subprocess.call("rm lb.xml", shell=True)
	subprocess.call("rm c1.qcow2", shell=True)
	subprocess.call("rm lb.qcow2", shell=True)

	#Ver cuantos servidores hay que destruir
	f = open("count.txt", "r")
	nServer = int(f.readline())
	f.close()

	#Destruir servidores
	for server in range(1, nServer + 1):
		subprocess.call("sudo virsh destroy s"+str(server), shell=True)
		subprocess.call("sudo virsh undefine s"+str(server), shell=True)

	#Borrar ficheros asociados a servidores
	subprocess.call("rm s*.xml", shell=True)
	subprocess.call("rm s*.qcow2", shell=True)
	subprocess.call("rm count.txt", shell=True)


#Crea y configura el LB
def createLB():
	#Variable XML
	plantilla = etree.parse('plantilla-vm-p3.xml')
	
	#Imagen a usar
	sourceFile = plantilla.find('devices/disk/source')
	currentPath = os.getcwd()
	sourceFile.set("file", ''+str(currentPath)+'/lb.qcow2')
	
	#Cambia nombre de VM
	vmName = plantilla.find('name')
	vmName.text = "lb"

	#Cambio devices/interface1
	interface = plantilla.find('devices/interface')
	interface.find('source').set("bridge", "LAN1")

	#Cambio devices/interface2	
	interface2 = copy.deepcopy(interface)
	interface2.find('source').set("bridge", "LAN2")
	plantilla.find('devices').append(interface2)

	#Creo el nuevo lb.xml
	f = open('lb.xml', 'w')
	plantilla.write(f, encoding='UTF-8')

	#Copy-on-write de la imagen existente
	subprocess.call("qemu-img create -f qcow2 -b cdps-vm-base-p3.qcow2 lb.qcow2", shell=True)

	#Permisos
	subprocess.call("chmod 777 lb.xml", shell=True)
	subprocess.call("chmod 777 lb.qcow2", shell=True)

#Crea y configura el resto de VMs
def createNewVM(name, LAN):
	#Variable XML
	plantilla = etree.parse('plantilla-vm-p3.xml')

	#Imagen a usar
	sourceFile = plantilla.find('devices/disk/source')
	currentPath = os.getcwd()
	sourceFile.set("file", ''+str(currentPath)+'/'+name+'.qcow2')
	
	#Cambia nombre de VM	
	vmName = plantilla.find('name')
	vmName.text = name

	# Anade la VM a la subred correspondiente
   	sourceBridge = plantilla.find('devices/interface/source')
    	sourceBridge.set("bridge", LAN)
	
	#Creo el nuevo sx.xml
	plantilla.write(open(''+name+'.xml', 'w'), encoding = 'UTF-8')
	#print name

	#Copy-on-write de la imagen existente
	subprocess.call("qemu-img create -f qcow2 -b cdps-vm-base-p3.qcow2 "+name+".qcow2", shell=True)

	#Permisos
	subprocess.call("chmod 777 "+name+".xml", shell=True)
	subprocess.call("chmod 777 "+name+".qcow2", shell=True)

#Monitoriza VMs
def monitor(vm):
	subprocess.call("xterm -rv -sb -rightbar -fa monospace -fs 10 -title 'MONITOR "+vm+"' -e 'watch -n 5 sudo virsh dominfo "+vm+"' &", shell=True)


def ayuda():
	print("Este script automatiza la creacion del escenario de pruebas de balanceador de trafico de la segunda parte de la practica 3. \n")
	print("Para ejecutarlo necesitamos la opcion 'python pfinalp1 comando', siendo comando:\n")
	print("-Crear: las instancias de las maquinas virtuales.\n")
	print("-Arrancar: inicia las instancias y las pone en funcionamiento.\n")
	print("-Parar: deshace la accion de arrancar.\n")
	print("-Destruir: elimina todos los ficheros del virt-manager y elimina todos los archivos.\n")
	print("-Monitor: aporta informacion sobre la ejecucion de los programas.\n")

		
#Orden a ejecutar
param = sys.argv[1]






#Fichro status. 0, 1, o 2 Maquina de estados. Working
# 0 = No hay maquinas creadas
# 1 = Maquinas paradas
# 2 = Maquinas arrancadas

#if os.path.isfile("status.txt"):
#	print("Existe el fichero")
#else:
#	statusFile = open("status.txt", "w")
#	statusFile.write("0"+"\n")
#	statusFile.close()

#statusFile = open("status.txt", "r")
#status = int(statusFile.readline())


#Ejecutar param o saco error
if param ==  "crear":
	nServer = 2

	#Acotamos servidores
	if len(sys.argv) == 3:
		if int(sys.argv[2]) > 5:
			nServer = 5
		elif int(sys.argv[2]) == 0:
			nServer = 2
		else:
			nServer = int(sys.argv[2])
	fnum = open("count.txt", "w")
	fnum.write(str(nServer)+"\n")
	fnum.close()
	crear(nServer)
	#statusFile = open("status.txt", "w")
	#statusFile.write("1"+"\n")
	#statusFile.close()
	

elif param == "arrancar":
	if len(sys.argv) == 3:
		arrancar(sys.argv[2])
	else:
		arrancar("")
	#statusFile = open("status.txt", "w")
	#statusFile.write("2"+"\n")
	#statusFile.close()
	

elif param == "parar":

	if len(sys.argv) == 3:
		parar(sys.argv[2])
	else:
		parar("")	
	#statusFile = open("status.txt", "w")
	#statusFile.write("1"+"\n")
	#statusFile.close()
	

elif param == "destruir":
	destruir()
	#statusFile = open("status.txt", "w")
	#statusFile.write("0"+"\n")
	#statusFile.close()

elif param == "monitor":
	if len(sys.argv) == 3:
		monitor(sys.argv[2])
	else:
		sys.stderr.write("Introduce el nombre de una de las VM\n")


elif param == "ayuda":
	ayuda()
	
	
else:
	sys.stderr.write("Introduccion del comando erronea\n")

