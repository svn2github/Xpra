#!/bin/bash

VERSION=$1
if [ -z "${VERSION}" ]; then
	VERSION=`PYTHONPATH="./src" python -c "from xpra import __version__; print(__version__)"`
fi
DIR=xpra-${VERSION}
rm -f "src/xpra/build_info.py"
cp -apr src ${DIR}
rm -fr "${DIR}/build"
rm -fr "${DIR}/install"
rm -f "${DIR}/xpra/wait_for_x_server.c"
rm -fr "${DIR}/wimpiggy/lowlevel/bindings.c"
rm -fr "${DIR}/wimpiggy/lowlevel/constants.pxi"
pushd "${DIR}"
svn info > ./svn-info
popd
find ${DIR} -name ".svn" -exec rm -fr {} \; 2>&1 | grep -v "No such file or directory"
find ${DIR} -name ".pyc" -exec rm -fr {} \;

RAW_SVN_VERSION=`svnversion`
SVN_REVISION=`python -c "x=\"$RAW_SVN_VERSION\";y=x.split(\":\");y.reverse();z=y[0];print \"\".join([c for c in z if c in \"0123456789\"])"`
for module in xpra wimpiggy parti; do
	file="${DIR}/${module}/__init__.py"
	echo "adding svn revision ${SVN_REVISION} to ${file}"
	sed -i -e "s+unknown+${SVN_REVISION}+" "${file}"
done

tar -jcf ${DIR}.tar.bz2 ${DIR} --exclude install --exclude build --exclude dist --exclude Output --exclude deb --exclude MANIFEST --exclude xpra/wait_for_x_server.c --exclude wimpiggy/lowlevel/wimpiggy.lowlevel.bindings.dep --exclude wimpiggy/lowlevel/constants.pxi --exclude wimpiggy/lowlevel/bindings.c --exclude *pyc
ls -al ${DIR}.tar.bz2
rm -fr "${DIR}"
